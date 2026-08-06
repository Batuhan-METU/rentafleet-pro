"""AI Filo Danışmanı servisi (RentA-Fleet PRO).

Anlık filo analitiği, bakım uyarıları ve anomali verilerini bağlama dönüştürür;
OpenAI streaming veya simüle akışlı Türkçe fallback yanıtı üretir.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from django.conf import settings

from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.analytics.analytics_service import get_fleet_analytics
from backend.infrastructure.services.analytics.maintenance_service import (
    STATUS_CRITICAL,
    get_maintenance_alerts,
)
from backend.infrastructure.services.analytics.scoring_service import SAFE_DRIVER_THRESHOLD
from backend.infrastructure.services.cost_calculation.floor_price_service import build_floor_price

logger = logging.getLogger(__name__)

# --- Talep/fiyat bağlamı eşikleri ---------------------------------------
# Not: bu eşikler yalnızca AI bağlamındaki "talep durumu" etiketini
# (yüksek/düşük/normal) belirler; gerçek fiyat artık gerçek maliyet
# motorundan (cost_calculation) geliyor.
HIGH_OCCUPANCY_THRESHOLD: float = 80.0
LOW_OCCUPANCY_THRESHOLD: float = 30.0
HIGH_MILEAGE_KM: int = 100_000

FALLBACK_STREAM_DELAY_SEC = 0.028


@dataclass
class FleetContext:
    """LLM'e verilecek toplulaştırılmış filo bağlamı."""

    total: int = 0
    rented: int = 0
    available: int = 0
    maintenance: int = 0
    occupancy_rate: float = 0.0
    avg_score: float = 0.0
    risky_count: int = 0
    lowest_score: int = 0
    lowest_score_driver: str = "—"
    anomaly_vehicle_count: int = 0
    critical_anomaly_count: int = 0
    top_risky_drivers: list[str] = field(default_factory=list)
    high_mileage_count: int = 0
    avg_suggested_price: float = 0.0
    demand_state: str = "normal"
    maintenance_alert_count: int = 0
    critical_maintenance_count: int = 0
    top_maintenance_plates: list[str] = field(default_factory=list)


def _demand_state(occupancy: float) -> str:
    if occupancy > HIGH_OCCUPANCY_THRESHOLD:
        return "yüksek"
    if occupancy < LOW_OCCUPANCY_THRESHOLD:
        return "düşük"
    return "normal"


def _average_daily_floor_price(vehicle_qs) -> float:
    """Filodaki hesaplanabilir araçların ortalama günlük kurtaran fiyatı (§6).

    Maliyet verisi eksik olan araçlar (§1.5 — Bilinmiyor ≠ Sıfır) ortalamaya
    dahil edilmez; hiçbiri hesaplanamıyorsa 0.0 döner (diğer FleetContext
    alanlarıyla aynı "veri yoksa 0.0" konvansiyonu).
    """
    prices = [
        float(floor.daily_floor_price)
        for vehicle in vehicle_qs
        if (floor := build_floor_price(vehicle)).daily_floor_price is not None
    ]
    return round(sum(prices) / len(prices), 2) if prices else 0.0


def _build_fleet_context(company_id: int) -> FleetContext:
    """Analytics, bakım ve anomali servislerinden anlık özet üretir."""
    analytics = get_fleet_analytics(company_id)
    maintenance_alerts = get_maintenance_alerts(company_id)

    if analytics.total == 0:
        return FleetContext()

    vehicle_qs = Vehicle.objects.filter(company_id=company_id)
    high_mileage = vehicle_qs.filter(current_km__gt=HIGH_MILEAGE_KM).count()
    demand_state = _demand_state(analytics.occupancy_rate)
    avg_price = _average_daily_floor_price(vehicle_qs)

    risky_count = sum(
        1 for d in analytics.lowest_drivers if d.get("skor", 100) < SAFE_DRIVER_THRESHOLD
    )
    top_risky = [
        d["ad_soyad"]
        for d in analytics.lowest_drivers
        if d.get("skor", 100) < SAFE_DRIVER_THRESHOLD
    ][:5]

    lowest_driver = "—"
    lowest_score = 0
    if analytics.lowest_drivers:
        lowest_driver = analytics.lowest_drivers[0].get("ad_soyad", "—")
        lowest_score = int(analytics.lowest_drivers[0].get("skor", 0))

    critical_maint = sum(1 for a in maintenance_alerts if a.status == STATUS_CRITICAL)
    top_maint_plates = [a.plate for a in maintenance_alerts[:5]]

    return FleetContext(
        total=analytics.total,
        rented=analytics.rented,
        available=analytics.available,
        maintenance=analytics.maintenance,
        occupancy_rate=analytics.occupancy_rate,
        avg_score=analytics.avg_score,
        risky_count=risky_count,
        lowest_score=lowest_score,
        lowest_score_driver=lowest_driver,
        anomaly_vehicle_count=analytics.critical_count,
        critical_anomaly_count=analytics.critical_count,
        top_risky_drivers=top_risky,
        high_mileage_count=high_mileage,
        avg_suggested_price=round(avg_price, 2),
        demand_state=demand_state,
        maintenance_alert_count=len(maintenance_alerts),
        critical_maintenance_count=critical_maint,
        top_maintenance_plates=top_maint_plates,
    )


def _context_summary_text(ctx: FleetContext) -> str:
    return (
        "ANLIK FİLO BAĞLAMI (gizli — kullanıcıya ham veri listeleme, yorumla):\n"
        f"- Toplam araç: {ctx.total} | Kirada: {ctx.rented} | Müsait: {ctx.available} | "
        f"Bakımda: {ctx.maintenance}\n"
        f"- Doluluk: %{ctx.occupancy_rate} (talep: {ctx.demand_state})\n"
        f"- Ortalama sürücü skoru: {ctx.avg_score}/100\n"
        f"- Riskli sürücü (skor<{SAFE_DRIVER_THRESHOLD}): {ctx.risky_count} — "
        f"{', '.join(ctx.top_risky_drivers) or 'yok'}\n"
        f"- En düşük skor: {ctx.lowest_score} ({ctx.lowest_score_driver})\n"
        f"- Kritik anomali olan araç: {ctx.critical_anomaly_count}\n"
        f"- Bakım uyarısı: {ctx.maintenance_alert_count} araç "
        f"(acil: {ctx.critical_maintenance_count}) — "
        f"plakalar: {', '.join(ctx.top_maintenance_plates) or 'yok'}\n"
        f"- 100.000 km üzeri araç: {ctx.high_mileage_count}\n"
        f"- Ortalama önerilen günlük fiyat: {ctx.avg_suggested_price} TL\n"
    )


def _openai_client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None
    # Açık bir timeout olmadan SDK'nın varsayılanı (dakikalarca) kullanılırdı
    # — OpenAI yavaş/asılı kalırsa bu istek için ayrılmış senkron Django
    # worker'ı gereğinden çok uzun süre kilitlenirdi (bkz. üretim sertleştirme
    # denetimi). Çağıranın kendi hata yakalaması zaten deterministik,
    # veriye dayalı bir yedeğe (fallback) düşüyor.
    return OpenAI(api_key=api_key, timeout=20.0, max_retries=1)


_TR_ASCII = str.maketrans("çğıöşüâî", "cgiosuai")


def _normalize(text: str) -> str:
    return text.casefold().translate(_TR_ASCII)


def _detect_intent(query: str) -> str:
    q = _normalize(query)
    if any(k in q for k in ("risk", "tehlike", "guvenlik", "anomali", "hirsiz")):
        return "risk"
    if any(k in q for k in ("bakim", "servis", "onarim", "kilometre", "yipran")):
        return "maintenance"
    if any(k in q for k in ("fiyat", "ucret", "gelir", "kazanc", "kar", "fiyatlandirma")):
        return "pricing"
    if any(k in q for k in ("skor", "surucu", "puan", "surus")):
        return "score"
    if any(k in q for k in ("doluluk", "kiralama", "talep", "musait", "bos")):
        return "occupancy"
    return "general"


def _fallback_response(query: str, ctx: FleetContext) -> str:
    if ctx.total == 0:
        return (
            "Şu anda filoda kayıtlı araç bulunmuyor. Analiz yapabilmem için önce "
            "araç ve telemetri verilerinin sisteme yüklenmesi gerekiyor."
        )

    intent = _detect_intent(query)

    if intent == "risk":
        names = ", ".join(ctx.top_risky_drivers) if ctx.top_risky_drivers else "belirgin risk yok"
        return (
            f"**Güvenlik özeti:** {ctx.critical_anomaly_count} araçta kritik anomali, "
            f"{ctx.risky_count} riskli sürücü tespit edildi.\n\n"
            f"**Öncelik:** {names}\n\n"
            "**Aksiyon:** Kritik anomalili araçları saha ekibine yönlendirin; en düşük skorlu "
            f"sürücü ({ctx.lowest_score_driver}, {ctx.lowest_score} puan) için uyarı süreci başlatın."
        )
    if intent == "maintenance":
        plates = ", ".join(ctx.top_maintenance_plates) or "—"
        return (
            f"**Bakım durumu:** {ctx.maintenance_alert_count} araç uyarıda "
            f"({ctx.critical_maintenance_count} acil). 100.000 km üzeri: {ctx.high_mileage_count} araç.\n\n"
            f"**Öncelikli plakalar:** {plates}\n\n"
            "**Aksiyon:** Acil bakım araçlarını servise alın; yüksek km'li araçlarda fren/lastik kontrolü planlayın."
        )
    if intent == "pricing":
        tip = (
            "Talep yüksek — fiyatları kademeli artırın."
            if ctx.demand_state == "yüksek"
            else (
                "Talep düşük — kampanya ve esnek fiyatla doluluğu artırın."
                if ctx.demand_state == "düşük"
                else "Talep dengeli — mevcut stratejiyi koruyun."
            )
        )
        return (
            f"**Piyasa:** Doluluk %{ctx.occupancy_rate} ({ctx.demand_state} talep). "
            f"Ortalama önerilen fiyat {ctx.avg_suggested_price} TL.\n\n"
            f"**Öneri:** {tip}"
        )
    if intent == "score":
        return (
            f"**Sürücü kalitesi:** Ortalama skor {ctx.avg_score}/100, "
            f"{ctx.risky_count} riskli sürücü.\n\n"
            f"**Öncelik:** {ctx.lowest_score_driver} ({ctx.lowest_score} puan)\n\n"
            "**Aksiyon:** Düşük skorlu sürücülere eko-sürüş eğitimi ve performans geri bildirimi verin."
        )
    if intent == "occupancy":
        return (
            f"**Doluluk:** {ctx.rented} kirada, {ctx.available} müsait, {ctx.maintenance} bakımda "
            f"(%{ctx.occupancy_rate}).\n\n"
            "**Aksiyon:** "
            + (
                "Bakımdaki araçları hızla devreye alın."
                if ctx.demand_state == "yüksek"
                else "Pazarlama ve fiyat esnekliğiyle müsait araçları değerlendirin."
            )
        )

    return (
        f"**Filo özeti:** {ctx.total} araç, doluluk %{ctx.occupancy_rate}, "
        f"ortalama skor {ctx.avg_score}/100, {ctx.critical_anomaly_count} kritik anomali, "
        f"{ctx.maintenance_alert_count} bakım uyarısı.\n\n"
        "**Öneri:** Kritik güvenlik ve acil bakımı önceliklendirin; talep durumuna göre "
        "dinamik fiyatlandırmayı aktif kullanın."
    )


def _simulate_stream(text: str, *, delay: float = FALLBACK_STREAM_DELAY_SEC) -> Iterator[str]:
    """Fallback metnini kelime kelime akıtır."""
    tokens = re.findall(r"\S+\s*|\n", text)
    for token in tokens:
        yield token
        time.sleep(delay)


