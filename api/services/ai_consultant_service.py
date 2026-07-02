"""AI Filo Danışmanı servisi (RentA-Fleet PRO — Day 8).

Diğer servislerden (sürücü skoru, anomali, fiyatlandırma) ve ilişkisel
veritabanından (doluluk) anlık istatistikleri toplar, bunları bir bağlam
(context) özetine dönüştürür ve bir LLM'e iletir.

OpenAI anahtarı tanımlıysa gerçek bir model çağrısı yapılır; tanımlı değilse
(veya çağrı başarısız olursa) fallback devreye girer: bağlamı okuyup
kullanıcının sorusunu analiz eden, tamamen Türkçe, kurumsal ve veriye dayalı
profesyonel bir yanıt üretir.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from django.conf import settings

from api.models import Driver, Vehicle, VehicleStatus
from api.services.anomaly_service import detect_vehicle_anomalies
from api.services.pricing_service import (
    BASE_PRICE,
    HIGH_DEMAND_MULTIPLIER,
    HIGH_MILEAGE_KM,
    HIGH_MILEAGE_PENALTY,
    HIGH_OCCUPANCY_THRESHOLD,
    LOW_DEMAND_MULTIPLIER,
    LOW_OCCUPANCY_THRESHOLD,
)
from api.services.scoring_service import SAFE_DRIVER_THRESHOLD, calculate_driver_score

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TR = (
    "Sen RentA-Fleet PRO platformunun kıdemli filo yönetimi danışmanısın. "
    "Sana sunulan anlık filo verilerini kullanarak, yöneticiye Türkçe, "
    "profesyonel, somut ve eyleme dönük tavsiyeler ver. Uydurma veri kullanma; "
    "yalnızca verilen istatistiklere dayan."
)


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


@contextmanager
def _quiet_service_logs() -> Iterator[None]:
    """Toplu (fleet-wide) tarama sırasında alt servislerin araç-başı fallback
    uyarılarını susturur; yoksa tek bir sohbet isteği yüzlerce log satırı üretir.
    """
    names = (
        "api.services.scoring_service",
        "api.services.anomaly_service",
        "api.services.fuel_service",
    )
    loggers = [logging.getLogger(name) for name in names]
    previous = [lg.level for lg in loggers]
    for lg in loggers:
        lg.setLevel(logging.ERROR)
    try:
        yield
    finally:
        for lg, level in zip(loggers, previous):
            lg.setLevel(level)


def _demand_state(occupancy: float) -> tuple[str, float]:
    """Doluluk oranından talep durumu ve fiyat çarpanını döndürür."""
    if occupancy > HIGH_OCCUPANCY_THRESHOLD:
        return "yüksek", HIGH_DEMAND_MULTIPLIER
    if occupancy < LOW_OCCUPANCY_THRESHOLD:
        return "düşük", LOW_DEMAND_MULTIPLIER
    return "normal", 1.0


def _build_fleet_context() -> FleetContext:
    """Tüm servislerden anlık veriyi toplayıp bağlam nesnesi üretir."""
    vehicles = list(Vehicle.objects.values("id", "plate_number", "current_km", "status"))
    total = len(vehicles)
    if total == 0:
        return FleetContext()

    rented = sum(1 for v in vehicles if v["status"] == VehicleStatus.RENTED)
    available = sum(1 for v in vehicles if v["status"] == VehicleStatus.AVAILABLE)
    maintenance = sum(1 for v in vehicles if v["status"] == VehicleStatus.MAINTENANCE)
    occupancy = (rented / total) * 100.0
    high_mileage = sum(1 for v in vehicles if (v["current_km"] or 0) > HIGH_MILEAGE_KM)

    drivers = list(Driver.objects.values("id", "first_name", "last_name"))
    scores: list[int] = []
    risky: list[tuple[str, int]] = []  # (ad_soyad, skor)
    anomaly_vehicle_count = 0
    critical_anomaly_count = 0

    with _quiet_service_logs():
        for driver in drivers:
            score = calculate_driver_score(driver["id"]).score
            scores.append(score)
            name = f"{driver['first_name']} {driver['last_name']}"
            if score < SAFE_DRIVER_THRESHOLD:
                risky.append((name, score))

        for vehicle in vehicles:
            anomalies = detect_vehicle_anomalies(vehicle["id"])
            has_critical = any(a.level == "KRITIK" for a in anomalies)
            if anomalies:
                anomaly_vehicle_count += 1
                if has_critical:
                    critical_anomaly_count += 1

    avg_score = sum(scores) / len(scores) if scores else 0.0
    risky_count = sum(1 for s in scores if s < SAFE_DRIVER_THRESHOLD)
    lowest_driver_name = "—"
    lowest_score = 0
    if drivers and scores:
        lowest_idx = min(range(len(scores)), key=lambda i: scores[i])
        lowest_score = scores[lowest_idx]
        d = drivers[lowest_idx]
        lowest_driver_name = f"{d['first_name']} {d['last_name']}"

    risky.sort(key=lambda item: item[1])
    top_risky_drivers = [item[0] for item in risky[:5]]

    demand_state, multiplier = _demand_state(occupancy)
    avg_price = (BASE_PRICE * multiplier) - (HIGH_MILEAGE_PENALTY * high_mileage / total)

    return FleetContext(
        total=total,
        rented=rented,
        available=available,
        maintenance=maintenance,
        occupancy_rate=round(occupancy, 1),
        avg_score=round(avg_score, 1),
        risky_count=risky_count,
        lowest_score=lowest_score,
        lowest_score_driver=lowest_driver_name,
        anomaly_vehicle_count=anomaly_vehicle_count,
        critical_anomaly_count=critical_anomaly_count,
        top_risky_drivers=top_risky_drivers,
        high_mileage_count=high_mileage,
        avg_suggested_price=round(avg_price, 2),
        demand_state=demand_state,
    )


def _context_summary_text(ctx: FleetContext) -> str:
    """Bağlamı LLM'e verilecek kısa, okunabilir bir metne dönüştürür."""
    return (
        "ANLIK FİLO VERİLERİ:\n"
        f"- Toplam araç: {ctx.total} (Kirada: {ctx.rented}, Müsait: {ctx.available}, "
        f"Bakımda: {ctx.maintenance})\n"
        f"- Doluluk oranı: %{ctx.occupancy_rate} (talep: {ctx.demand_state})\n"
        f"- Ortalama sürücü skoru: {ctx.avg_score}/100\n"
        f"- Riskli sürücü sayısı (skor<{SAFE_DRIVER_THRESHOLD}): {ctx.risky_count}\n"
        f"- En düşük skor: {ctx.lowest_score} ({ctx.lowest_score_driver})\n"
        f"- Anomalili araç: {ctx.anomaly_vehicle_count} "
        f"(kritik: {ctx.critical_anomaly_count})\n"
        f"- En riskli sürücüler: {', '.join(ctx.top_risky_drivers) or 'yok'}\n"
        f"- 100.000 km üzeri araç: {ctx.high_mileage_count}\n"
        f"- Ortalama önerilen fiyat: {ctx.avg_suggested_price} TL\n"
    )


# ----------------------------------------------------------------------
# OpenAI entegrasyonu (anahtar varsa)
# ----------------------------------------------------------------------
def _try_openai(user_query: str, context_text: str) -> str | None:
    """OpenAI anahtarı varsa gerçek model çağrısını dener; aksi halde None."""
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TR},
                {"role": "user", "content": f"{context_text}\n\nKullanıcı sorusu: {user_query}"},
            ],
            temperature=0.4,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - any failure => fallback
        logger.warning("OpenAI çağrısı başarısız, fallback'e geçiliyor: %s", exc)
        return None


# ----------------------------------------------------------------------
# Gelişmiş LLM taklidi (fallback)
# ----------------------------------------------------------------------
_TR_ASCII = str.maketrans("çğıöşüâî", "cgiosuai")


def _normalize(text: str) -> str:
    """Türkçe karakterleri ASCII'ye indirger ki 'bakım'/'bakim' gibi
    yazımlar da niyet eşleşmesinde yakalanabilsin."""
    return text.casefold().translate(_TR_ASCII)


def _detect_intent(query: str) -> str:
    """Kullanıcı sorusundan niyeti çıkarır (Türkçe karaktere duyarsız)."""
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
    """Bağlama ve niyete duyarlı, kurumsal Türkçe analiz metni üretir."""
    if ctx.total == 0:
        return (
            "Şu anda filoda kayıtlı araç bulunmuyor. Analiz yapabilmem için önce "
            "araç ve telemetri verilerinin sisteme yüklenmesi gerekiyor."
        )

    intent = _detect_intent(query)
    header = "🤖 Filo Danışmanı Analizi\n\n"

    if intent == "risk":
        names = ", ".join(ctx.top_risky_drivers) if ctx.top_risky_drivers else "belirgin bir risk yok"
        body = (
            f"Güvenlik analizine göre filodaki {ctx.total} aracın "
            f"{ctx.anomaly_vehicle_count} tanesinde anomali tespit edildi; bunların "
            f"{ctx.critical_anomaly_count} tanesi KRİTİK seviyede. Skoru "
            f"{SAFE_DRIVER_THRESHOLD} altındaki riskli sürücü sayısı {ctx.risky_count}.\n\n"
            f"Öncelik verilmesi gereken sürücüler: {names}.\n\n"
            "Önerim: Kritik anomalisi olan araçları derhal saha ekibine yönlendirin, "
            "gece hareketliliği gösteren araçlarda GPS/immobilizer kontrolü yapın ve "
            f"en düşük skorlu araç ({ctx.lowest_score_driver}, skor {ctx.lowest_score}) "
            "için sürücü uyarı/eğitim süreci başlatın."
        )
    elif intent == "maintenance":
        body = (
            f"Filodaki {ctx.total} araçtan {ctx.high_mileage_count} tanesi 100.000 km "
            f"üzerinde ve {ctx.maintenance} araç halihazırda bakımda. Ortalama sürücü "
            f"skoru {ctx.avg_score}/100; düşük skor genelde sert kullanım ve daha sık "
            "bakım ihtiyacı demektir.\n\n"
            "Önerim: 100.000 km üzeri araçlar için proaktif (fren, lastik, motor) bakım "
            f"planı oluşturun. Skoru {SAFE_DRIVER_THRESHOLD} altındaki {ctx.risky_count} "
            "araca öncelik verin; bu araçlarda aşınma riski daha yüksektir."
        )
    elif intent == "pricing":
        body = (
            f"Filo doluluk oranı %{ctx.occupancy_rate} ({ctx.demand_state} talep). "
            f"Ortalama önerilen günlük fiyat {ctx.avg_suggested_price} TL.\n\n"
            "Önerim: "
            + (
                "Talep yüksek; dinamik fiyatları kademeli artırarak gelir maksimizasyonu "
                "yapabilirsiniz."
                if ctx.demand_state == "yüksek"
                else (
                    "Talep düşük; kısa vadeli kampanya ve indirimlerle doluluğu artırmayı "
                    "hedefleyin."
                    if ctx.demand_state == "düşük"
                    else "Talep dengeli; mevcut fiyat stratejisini koruyabilir, yüksek "
                    "kilometreli araçlarda küçük indirimlerle dönüşü hızlandırabilirsiniz."
                )
            )
        )
    elif intent == "score":
        body = (
            f"Filo ortalama sürücü skoru {ctx.avg_score}/100. Skoru "
            f"{SAFE_DRIVER_THRESHOLD} altındaki {ctx.risky_count} araç agresif sürüş "
            f"sergiliyor; en düşük skor {ctx.lowest_score} ({ctx.lowest_score_driver}).\n\n"
            "Önerim: Düşük skorlu sürücülere geri bildirim ve eko-sürüş eğitimi verin; "
            "skor iyileşmesi hem yakıt hem bakım maliyetini düşürecektir."
        )
    elif intent == "occupancy":
        body = (
            f"Şu an {ctx.rented} araç kirada, {ctx.available} araç müsait, "
            f"{ctx.maintenance} araç bakımda. Doluluk oranı %{ctx.occupancy_rate} "
            f"({ctx.demand_state} talep).\n\n"
            "Önerim: "
            + (
                "Doluluk yüksek; bakımdaki araçları hızla devreye alıp ek talebi karşılayın."
                if ctx.demand_state == "yüksek"
                else "Müsait araç fazlalığı var; pazarlama ve fiyat esnekliğiyle doluluğu "
                "yükseltmeye odaklanın."
            )
        )
    else:
        body = (
            f"Filonuzda {ctx.total} araç bulunuyor (doluluk %{ctx.occupancy_rate}, "
            f"{ctx.demand_state} talep). Ortalama sürücü skoru {ctx.avg_score}/100, "
            f"riskli sürücü sayısı {ctx.risky_count} ve {ctx.anomaly_vehicle_count} araçta "
            f"anomali ({ctx.critical_anomaly_count} kritik) mevcut. Ortalama önerilen "
            f"fiyat {ctx.avg_suggested_price} TL.\n\n"
            "Genel önerim: Kritik güvenlik anomalilerini önceliklendirin, yüksek "
            "kilometreli araçlarda proaktif bakım planlayın ve talep durumuna göre "
            "dinamik fiyatlandırmayı aktif kullanın."
        )

    return header + body


def get_ai_fleet_advice(user_query: str) -> str:
    """Kullanıcı sorusuna, anlık filo verisine dayalı AI yanıtı üretir."""
    query = (user_query or "").strip()
    context = _build_fleet_context()
    context_text = _context_summary_text(context)

    ai_response = _try_openai(query, context_text)
    if ai_response:
        return ai_response

    return _fallback_response(query, context)
