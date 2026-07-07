"""Dinamik fiyatlandırma servisi (RentA-Fleet PRO — Day 7).

Bir aracın günlük önerilen kiralama fiyatını, filonun anlık doluluk oranına
ve aracın kilometresine göre hesaplar. Veriler tamamen ilişkisel veritabanından
(PostgreSQL/SQLite) geldiği için ClickHouse'a bağımlılık yoktur.

Kurallar:
  * Taban fiyat: 1500 TL.
  * Doluluk > %80  -> +%25 (yüksek talep).
  * Doluluk < %30  -> -%15 (düşük sezon indirimi).
  * current_km > 100.000 -> -50 TL (yüksek kilometre cezası).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.models import Vehicle, VehicleStatus

# --- Fiyatlandırma parametreleri --------------------------------------
BASE_PRICE: float = 1500.0
HIGH_OCCUPANCY_THRESHOLD: float = 80.0
LOW_OCCUPANCY_THRESHOLD: float = 30.0
HIGH_DEMAND_MULTIPLIER: float = 1.25
LOW_DEMAND_MULTIPLIER: float = 0.85
HIGH_MILEAGE_KM: int = 100_000
HIGH_MILEAGE_PENALTY: float = 50.0


@dataclass(frozen=True)
class PricingResult:
    """Önerilen fiyat hesabının yapısal sonucu (değişmez)."""

    vehicle_id: int
    base_price: float
    final_price: float
    reason: str
    occupancy_rate: float


def _fleet_occupancy_rate(company_id: int) -> float:
    """Şirket filosunun doluluk oranını yüzde olarak hesaplar."""
    total = Vehicle.objects.filter(company_id=company_id).count()
    if total == 0:
        return 0.0
    rented = Vehicle.objects.filter(
        company_id=company_id,
        status=VehicleStatus.RENTED,
    ).count()
    return (rented / total) * 100.0


def calculate_suggested_price(
    vehicle_id: int,
    *,
    company_id: int | None = None,
) -> PricingResult:
    """Verilen araç için dinamik önerilen fiyatı hesaplar.

    :raises Vehicle.DoesNotExist: araç bulunamazsa.
    """
    vehicle = Vehicle.objects.only("id", "current_km", "company_id").get(pk=vehicle_id)
    scoped_company_id = company_id or vehicle.company_id

    occupancy = _fleet_occupancy_rate(scoped_company_id)
    occupancy_pct = round(occupancy)
    price = BASE_PRICE

    if occupancy > HIGH_OCCUPANCY_THRESHOLD:
        price *= HIGH_DEMAND_MULTIPLIER
        reason = (
            f"Filo doluluk oranı %{occupancy_pct} olduğu için yüksek talep "
            "fiyatlandırması uygulandı."
        )
    elif occupancy < LOW_OCCUPANCY_THRESHOLD:
        price *= LOW_DEMAND_MULTIPLIER
        reason = (
            f"Filo doluluk oranı %{occupancy_pct} olduğu için düşük sezon "
            "indirimi uygulandı."
        )
    else:
        reason = (
            f"Filo doluluk oranı %{occupancy_pct} normal seviyede; taban fiyat uygulandı."
        )

    if (vehicle.current_km or 0) > HIGH_MILEAGE_KM:
        price -= HIGH_MILEAGE_PENALTY
        reason += (
            f" Yüksek kilometre (100.000 km üzeri) nedeniyle "
            f"{int(HIGH_MILEAGE_PENALTY)} TL indirim uygulandı."
        )

    return PricingResult(
        vehicle_id=vehicle.pk,
        base_price=BASE_PRICE,
        final_price=round(price, 2),
        reason=reason,
        occupancy_rate=round(occupancy, 1),
    )
