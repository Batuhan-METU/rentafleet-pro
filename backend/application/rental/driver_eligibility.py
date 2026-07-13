"""Rezervasyon akışı için sürücü–araç uygunluk kontrolleri."""

from __future__ import annotations

from rest_framework.exceptions import ValidationError

from backend.domain.eligibility.engine import is_vehicle_eligible_for_risk_level
from backend.apps.customer_profiles.models import Driver
from backend.apps.vehicles.models import Vehicle


def _latest_risk_audit(driver: Driver) -> dict:
    snapshot = driver.risk_snapshots.order_by("-computed_at").first()
    if snapshot is None:
        return {}

    breakdown = snapshot.factor_breakdown if isinstance(snapshot.factor_breakdown, dict) else {}
    audit = breakdown.get("audit") if isinstance(breakdown.get("audit"), dict) else {}
    if not audit and "blockers" in breakdown:
        return breakdown
    return audit if isinstance(audit, dict) else {}


def driver_risk_cleared(driver: Driver) -> bool:
    """Risk kural motoru blokajsız onay — Findeks/kısıtlama engeli yok."""
    if driver.is_blacklisted:
        return False
    if driver.current_risk_score is None or not driver.risk_level:
        return False

    audit = _latest_risk_audit(driver)
    if not audit and driver.risk_snapshots.exists():
        return True
    return not audit.get("blockers", [])


def driver_has_risk_approval(driver: Driver) -> bool:
    """Genel kiralama onayı — blokaj yok ve en az bir uygun segment mevcut."""
    if not driver_risk_cleared(driver):
        return False

    snapshot = driver.risk_snapshots.order_by("-computed_at").first()
    if snapshot is None:
        return False

    breakdown = snapshot.factor_breakdown if isinstance(snapshot.factor_breakdown, dict) else {}
    eligible = breakdown.get("eligible_vehicles")
    if eligible is None:
        eligible = _latest_risk_audit(driver).get("eligible_vehicles", [])
    return bool(eligible)


def is_driver_eligible_for_vehicle(driver: Driver, vehicle: Vehicle) -> bool:
    """Sürücünün risk onayı ve araç segmenti uygunluğunu doğrular."""
    if not driver_risk_cleared(driver):
        return False
    return is_vehicle_eligible_for_risk_level(vehicle, driver.risk_level)


def assert_driver_eligible_for_vehicle(driver: Driver, vehicle: Vehicle) -> None:
    """Uygun değilse ``ValidationError`` fırlatır."""
    if driver.current_risk_score is None or not driver.risk_level:
        raise ValidationError(
            {"error": "Sürücünün risk skoru hesaplanmamış. Önce risk değerlendirmesi yapılmalıdır."}
        )

    if not driver_risk_cleared(driver):
        blockers = driver.risk_note or "Risk değerlendirmesi onaylanmadı."
        raise ValidationError(
            {"error": f"Sürücü risk skoru yetersiz olduğu için rezervasyon onaylanamaz: {blockers}"}
        )

    if not is_vehicle_eligible_for_risk_level(vehicle, driver.risk_level):
        raise ValidationError(
            {"error": "Seçilen araç, sürücünün risk seviyesine uygun segmentte değil."}
        )
