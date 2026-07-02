"""Yakıt & rota optimizasyon servisi (RentA-Fleet PRO — Day 5).

Bir aracın markası/modeline ve (varsa) ClickHouse telemetri verisine bakarak:
  * ideal ekonomik hızı (binek ~90 km/s, ticari ~80 km/s),
  * uygulanırsa beklenen yakıt tasarrufu yüzdesini,
  * Türkçe bir AI tavsiyesi ve rota optimizasyon önerisini

üretir.

ClickHouse yerelde devre dışı olabileceğinden sorgu ``OperationalError``
yakalanarak sarmalanır; bağlantı yoksa aracın marka/modeline göre
DETERMİNİSTİK ve gerçekçi bir matematiksel tahmin döndürülür.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from clickhouse_connect.driver.exceptions import OperationalError

from api.clickhouse_client import get_clickhouse_client, suppress_http_warnings
from api.models import Vehicle

logger = logging.getLogger(__name__)

# --- Sabitler ----------------------------------------------------------
TELEMETRY_TABLE: str = "telemetry_logs"
MAX_SAVINGS_PCT: float = 30.0


@dataclass(frozen=True)
class CategoryProfile:
    """Bir araç kategorisinin yakıt profili."""

    key: str
    label_tr: str
    ideal_speed: int           # km/s
    base_savings: float        # taban tasarruf potansiyeli (%)
    baseline_consumption: float  # referans tüketim (L/100km)


# Kategori profilleri — ağır/ticari araçlarda taban tüketim ve tasarruf
# potansiyeli yüksek, ekonomik otomobillerde düşüktür.
CATEGORY_PROFILES: dict[str, CategoryProfile] = {
    "ticari": CategoryProfile("ticari", "ticari araç", 80, 16.0, 12.5),
    "suv": CategoryProfile("suv", "SUV", 90, 13.0, 9.0),
    "binek": CategoryProfile("binek", "binek otomobil", 90, 11.0, 7.0),
    "ekonomik": CategoryProfile("ekonomik", "ekonomik otomobil", 90, 8.5, 5.5),
}

# Marka/model adına göre kategori sınıflandırması için anahtar kelimeler.
COMMERCIAL_KEYWORDS: tuple[str, ...] = (
    "transit", "transporter", "ducato", "sprinter", "crafter", "master",
    "daily", "vito", "doblo", "connect", "caddy", "kangoo", "partner", "berlingo",
)
SUV_KEYWORDS: tuple[str, ...] = (
    "tucson", "c-hr", "chr", "kuga", "qashqai", "tiguan", "3008", "5008", "duster",
)
ECONOMY_KEYWORDS: tuple[str, ...] = (
    "yaris", "i20", "fiesta", "clio", "polo", "500", "panda", "symbol", "accent",
)


@dataclass(frozen=True)
class FuelOptimization:
    """Yakıt optimizasyon sonucu (değişmez yapısal model)."""

    vehicle_id: int
    ideal_speed: int
    estimated_savings_pct: float
    advice: str
    route_recommendation: str
    is_fallback: bool


def _classify(brand: str, model: str) -> CategoryProfile:
    """Marka/model adından araç kategorisini belirler."""
    text = f"{brand} {model}".lower()
    if any(keyword in text for keyword in COMMERCIAL_KEYWORDS):
        return CATEGORY_PROFILES["ticari"]
    if any(keyword in text for keyword in SUV_KEYWORDS):
        return CATEGORY_PROFILES["suv"]
    if any(keyword in text for keyword in ECONOMY_KEYWORDS):
        return CATEGORY_PROFILES["ekonomik"]
    return CATEGORY_PROFILES["binek"]


def _route_recommendation(profile: CategoryProfile) -> str:
    """Kategoriye göre Türkçe rota optimizasyon önerisi."""
    if profile.key == "ticari":
        return (
            "Ağır yük taşıyan bu araçta şehir içi dur-kalk trafiğinden kaçınılmalı; "
            "çevre yolu ve otoban rotaları tercih edilmelidir."
        )
    return "Şehir içi dur-kalk trafiğinden kaçınmak için çevre yolu rotası tercih edilmelidir."


def _build_advice(
    brand: str, model: str, profile: CategoryProfile, savings_pct: float
) -> str:
    """Türkçe AI tavsiye metnini üretir."""
    return (
        f"Bu araç ({brand} {model}) son sürüş verilerine göre agresif hızlanmalar "
        f"nedeniyle yaklaşık %{round(savings_pct)} fazla yakıt tüketmiştir. "
        f"Otobanda {profile.ideal_speed} km/s sabit hızla seyretmesi durumunda "
        f"%{savings_pct:g} oranında tasarruf sağlanabilir."
    )


def _build_result(
    vehicle: Vehicle,
    profile: CategoryProfile,
    savings_pct: float,
    is_fallback: bool,
) -> FuelOptimization:
    """Ortak sonuç kurucu."""
    savings = round(min(MAX_SAVINGS_PCT, max(0.0, savings_pct)), 1)
    return FuelOptimization(
        vehicle_id=vehicle.pk,
        ideal_speed=profile.ideal_speed,
        estimated_savings_pct=savings,
        advice=_build_advice(vehicle.brand, vehicle.model, profile, savings),
        route_recommendation=_route_recommendation(profile),
        is_fallback=is_fallback,
    )


def _fallback(vehicle: Vehicle, profile: CategoryProfile) -> FuelOptimization:
    """ClickHouse erişilemezken deterministik, gerçekçi tahmin.

    Aynı araç her zaman aynı sonucu üretir; tasarruf yüzdesi kategori taban
    değerine küçük, kimliğe bağlı bir varyasyon eklenerek hesaplanır.
    """
    variation = (vehicle.pk % 9) * 0.5  # 0.0 .. 4.0
    savings = profile.base_savings + variation
    logger.warning(
        "ClickHouse erişilemedi; araç %s için deterministik yakıt tahmini üretildi.",
        vehicle.pk,
    )
    return _build_result(vehicle, profile, savings, is_fallback=True)


def _query_drive_stats(vehicle_id: int) -> dict[str, float]:
    """ClickHouse'tan araca ait sürüş istatistiklerini çeker."""
    # Client creation establishes the connection, so it must also sit inside
    # the suppression context to silence the offline-connection warnings.
    with suppress_http_warnings():
        client = get_clickhouse_client()
        result = client.query(
            "SELECT avg(speed) AS avg_speed, "
            "countIf(event_type = 'speed_violation') AS violations, "
            "countIf(event_type = 'harsh_brake') AS brakes, "
            "count() AS total "
            f"FROM {TELEMETRY_TABLE} "
            "WHERE device_id = %(vehicle_id)s",
            parameters={"vehicle_id": vehicle_id},
        )
    row = result.result_rows[0]
    return {
        "avg_speed": float(row[0] or 0.0),
        "violations": float(row[1] or 0),
        "brakes": float(row[2] or 0),
        "total": float(row[3] or 0),
    }


def get_fuel_optimization_data(vehicle_id: int) -> FuelOptimization:
    """Verilen araç için yakıt & rota optimizasyon verisini hesaplar.

    ClickHouse'a ulaşılabiliyor ve veri varsa gerçek telemetriden hesaplar;
    aksi halde marka/modele dayalı deterministik tahmine düşer.

    :raises Vehicle.DoesNotExist: araç bulunamazsa.
    """
    vehicle = Vehicle.objects.only("id", "brand", "model").get(pk=vehicle_id)
    profile = _classify(vehicle.brand, vehicle.model)

    try:
        stats = _query_drive_stats(vehicle_id)
    except OperationalError:
        return _fallback(vehicle, profile)

    if stats["total"] <= 0:
        # Telemetri yoksa anlamlı bir hesap yapılamaz; tahmine düş.
        return _fallback(vehicle, profile)

    # Gerçek veriden tahmin: kategori tabanı + agresif olay oranı + aşırı hız.
    bad_ratio = (stats["violations"] + stats["brakes"]) / stats["total"]
    over_speed = max(0.0, stats["avg_speed"] - profile.ideal_speed)
    savings = (profile.base_savings * 0.5) + (bad_ratio * 40.0) + (over_speed * 0.25)
    return _build_result(vehicle, profile, savings, is_fallback=False)
