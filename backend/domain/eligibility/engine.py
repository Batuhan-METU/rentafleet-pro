"""Araç uygunluk motoru — risk seviyesine göre segment.

Filodaki müsait araçları DB'den sorgulayıp öneri listesi kuran orkestrasyon
(``recommend_vehicles``) burada DEĞİL, application katmanındadır (bkz.
``backend.application.rental.driver_eligibility.recommend_vehicles``) —
domain katmanı ORM/infrastructure'a dokunmaz (audit bulgusu #20).
"""

from __future__ import annotations

from backend.apps.risk_checks.models import VehicleRiskTier
from backend.apps.vehicles.models import Vehicle
from backend.domain.shared.enums import RiskLevel, VehicleTier

RISK_TO_ALLOWED_TIERS: dict[RiskLevel, frozenset[VehicleTier]] = {
    RiskLevel.VERY_LOW: frozenset({VehicleTier.PREMIUM, VehicleTier.STANDARD, VehicleTier.ECONOMY}),
    RiskLevel.LOW: frozenset({VehicleTier.PREMIUM, VehicleTier.STANDARD, VehicleTier.ECONOMY}),
    RiskLevel.MEDIUM: frozenset({VehicleTier.STANDARD, VehicleTier.ECONOMY}),
    RiskLevel.HIGH: frozenset({VehicleTier.ECONOMY}),
    RiskLevel.VERY_HIGH: frozenset(),
}

PREMIUM_BRANDS = frozenset({"mercedes", "bmw", "audi", "tesla", "volvo", "lexus", "porsche"})
ECONOMY_BRANDS = frozenset({"dacia", "fiat", "renault", "hyundai", "peugeot", "opel", "citroen"})


def infer_vehicle_tier(vehicle: Vehicle) -> str:
    try:
        return vehicle.risk_tier.tier
    except VehicleRiskTier.DoesNotExist:
        pass

    brand = vehicle.brand.lower().strip()
    if brand in PREMIUM_BRANDS:
        return VehicleTier.PREMIUM
    if brand in ECONOMY_BRANDS or vehicle.segment.upper() in {"A", "B"}:
        return VehicleTier.ECONOMY
    return VehicleTier.STANDARD


def is_vehicle_eligible_for_risk_level(vehicle: Vehicle, risk_level: str) -> bool:
    """Aracın segmenti, verilen risk seviyesi için izin verilen tier kümesinde mi?"""
    try:
        level = RiskLevel(risk_level)
    except ValueError:
        return False

    allowed = RISK_TO_ALLOWED_TIERS.get(level, frozenset())
    if not allowed:
        return False

    return infer_vehicle_tier(vehicle) in allowed