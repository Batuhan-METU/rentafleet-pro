"""AI Filo Danışmanı servisi (RentA-Fleet PRO).

Anlık filo analitiği, bakım uyarıları ve anomali verilerini bağlama dönüştürür;
OpenAI streaming veya simüle akışlı Türkçe fallback yanıtı üretir.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Iterator

from django.conf import settings

from backend.infrastructure.services.analytics.analytics_service import get_fleet_analytics
from backend.infrastructure.services.analytics.maintenance_service import STATUS_CRITICAL, get_maintenance_alerts
from backend.infrastructure.services.pricing.pricing_service import (
    BASE_PRICE,
    HIGH_DEMAND_MULTIPLIER,
    HIGH_MILEAGE_KM,
    HIGH_MILEAGE_PENALTY,
    HIGH_OCCUPANCY_THRESHOLD,
    LOW_DEMAND_MULTIPLIER,
    LOW_OCCUPANCY_THRESHOLD,
)
from backend.infrastructure.services.analytics.scoring_service import SAFE_DRIVER_THRESHOLD
from backend.models import Vehicle

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TR = (
    "Sen RentA-Fleet PRO sisteminin kıdemli, veri odaklı AI Filo Danışmanısın. "
    "Karşındaki kişi bir Araç Kiralama Şirketi Müdürüdür. "
    "Cevapların her zaman profesyonel, Türkçe, kısa, net ve aksiyona dökülebilir olmalıdır. "
    "Yalnızca sana verilen anlık filo bağlamındaki sayılara ve listelere dayan; "
    "uydurma istatistik veya plaka üretme. "
    "Yanıt formatı: bölüm başlıklarını **kalın** yaz; somut önerileri `- ` ile madde listesi olarak ver."
)

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


def _demand_state(occupancy: float) -> tuple[str, float]:
    if occupancy > HIGH_OCCUPANCY_THRESHOLD:
        return "yüksek", HIGH_DEMAND_MULTIPLIER
    if occupancy < LOW_OCCUPANCY_THRESHOLD:
        return "düşük", LOW_DEMAND_MULTIPLIER
    return "normal", 1.0


def _build_fleet_context(company_id: int | None = None) -> FleetContext:
    """Analytics, bakım ve anomali servislerinden anlık özet üretir."""
    analytics = get_fleet_analytics(company_id=company_id)
    maintenance_alerts = get_maintenance_alerts(company_id=company_id)

    if analytics.total == 0:
        return FleetContext()

    vehicle_qs = Vehicle.objects.all()
    if company_id is not None:
        vehicle_qs = vehicle_qs.filter(company_id=company_id)
    high_mileage = vehicle_qs.filter(current_km__gt=HIGH_MILEAGE_KM).count()
    demand_state, multiplier = _demand_state(analytics.occupancy_rate)
    avg_price = (BASE_PRICE * multiplier) - (
        HIGH_MILEAGE_PENALTY * high_mileage / max(analytics.total, 1)
    )

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


def _openai_messages(user_query: str, context_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT_TR},
        {
            "role": "user",
            "content": (
                f"{context_text}\n\n"
                f"MÜDÜRÜN SORUSU: {user_query}\n\n"
                "Yukarıdaki bağlamı kullanarak kısa ve aksiyon odaklı yanıt ver."
            ),
        },
    ]


def _openai_client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _try_openai_stream(user_query: str, context_text: str) -> Iterator[str] | None:
    """OpenAI stream=True; başlatma hatasında None."""
    client = _openai_client()
    if client is None:
        return None

    try:
        stream = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")),
            messages=_openai_messages(user_query, context_text),
            temperature=0.35,
            stream=True,
        )
    except Exception as exc:
        logger.warning("OpenAI stream başlatılamadı, fallback'e geçiliyor: %s", exc)
        return None

    def _generator() -> Iterator[str]:
        for event in stream:
            delta = event.choices[0].delta.content
            if delta:
                yield delta

    return _generator()


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


def stream_ai_fleet_advice(
    user_query: str,
    *,
    company_id: int | None = None,
) -> Iterator[str]:
    """Kullanıcı sorusuna stream chunk'ları üretir."""
    query = (user_query or "").strip()
    context = _build_fleet_context(company_id=company_id)
    context_text = _context_summary_text(context)

    openai_stream = _try_openai_stream(query, context_text)
    if openai_stream is not None:
        received = False
        for chunk in openai_stream:
            received = True
            yield chunk
        if received:
            return

    yield from _simulate_stream(_fallback_response(query, context))


def stream_ai_fleet_advice_sse(
    user_query: str,
    *,
    company_id: int | None = None,
) -> Iterator[str]:
    """SSE formatında satırlar üretir."""
    try:
        for chunk in stream_ai_fleet_advice(user_query, company_id=company_id):
            payload = json.dumps({"content": chunk}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    except Exception as exc:
        logger.exception("AI danışman stream hatası")
        yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

