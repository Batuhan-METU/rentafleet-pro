"""Kiralama akışı için sürücü–araç uygunluk kontrolleri."""

from __future__ import annotations

from rest_framework.exceptions import ValidationError

from backend.apps.customer_profiles.models import Driver
from backend.apps.vehicles.models import Vehicle, VehicleStatus
from backend.domain.eligibility.engine import (
    RISK_TO_ALLOWED_TIERS,
    infer_vehicle_tier,
    is_vehicle_eligible_for_risk_level,
)
from backend.domain.shared.enums import RiskLevel
from backend.infrastructure.services.sipp.sipp_service import resolve_sipp


def _latest_risk_snapshot(driver: Driver):
    """En son risk anlık görüntüsü.

    PERFORMANS: `.all()` kullanır çünkü `DriverListView.get_queryset()`
    `risk_snapshots`'ı zaten `Prefetch(..., order_by("-computed_at"))` ile
    önceden yüklüyor — `.order_by()/.filter()/.exists()` gibi manager'a
    zincirlenen HERHANGİ bir çağrı bu önbelleği atlayıp HER sürücü için ayrı
    bir sorgu tetikler (N+1). `.all()` (ek filtre yokken) önbellek varsa onu
    kullanır; yoksa (ör. tekil sürücü detayı) modelin `Meta.ordering =
    ("-computed_at",)` sıralamasına düşer — davranış birebir aynı kalır.
    """
    snapshots = list(driver.risk_snapshots.all())
    return snapshots[0] if snapshots else None


def _audit_from_snapshot(snapshot) -> dict:
    if snapshot is None:
        return {}
    breakdown = snapshot.factor_breakdown if isinstance(snapshot.factor_breakdown, dict) else {}
    audit = breakdown.get("audit") if isinstance(breakdown.get("audit"), dict) else {}
    if not audit and "blockers" in breakdown:
        return breakdown
    return audit if isinstance(audit, dict) else {}


def _latest_risk_audit(driver: Driver) -> dict:
    return _audit_from_snapshot(_latest_risk_snapshot(driver))


def driver_risk_cleared(driver: Driver) -> bool:
    """Risk kural motoru blokajsız onay — Findeks/kısıtlama engeli yok."""
    if driver.is_blacklisted:
        return False
    if driver.current_risk_score is None or not driver.risk_level:
        return False

    snapshot = _latest_risk_snapshot(driver)
    audit = _audit_from_snapshot(snapshot)
    if not audit and snapshot is not None:
        return True
    return not audit.get("blockers", [])


def driver_has_risk_approval(driver: Driver) -> bool:
    """Genel kiralama onayı — blokaj yok ve en az bir uygun segment mevcut."""
    if not driver_risk_cleared(driver):
        return False

    snapshot = _latest_risk_snapshot(driver)
    if snapshot is None:
        return False

    breakdown = snapshot.factor_breakdown if isinstance(snapshot.factor_breakdown, dict) else {}
    eligible = breakdown.get("eligible_vehicles")
    if eligible is None:
        eligible = _audit_from_snapshot(snapshot).get("eligible_vehicles", [])
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
            {"error": f"Sürücü risk skoru yetersiz olduğu için kiralama onaylanamaz: {blockers}"}
        )

    if not is_vehicle_eligible_for_risk_level(vehicle, driver.risk_level):
        raise ValidationError(
            {"error": "Seçilen araç, sürücünün risk seviyesine uygun segmentte değil."}
        )


def recommend_vehicles(
    company_id: int,
    risk_level: str,
    *,
    limit: int = 500,
) -> list[dict]:
    """Risk seviyesinin izin verdiği segmentteki TÜM müsait araçları döner.

    ``limit`` yalnızca aşırı büyük filolarda güvenlik amaçlı bir üst sınırdır
    — normalde risk seviyesine uyan araçların TAMAMI dönmelidir (ör. Çok
    Düşük risk tüm segmentlere izin verdiği için, filodaki tüm müsait
    araçlar listelenir; sadece ilk birkaç tanesi değil).
    """
    try:
        level = RiskLevel(risk_level)
    except ValueError:
        return []

    allowed = RISK_TO_ALLOWED_TIERS.get(level, frozenset())
    if not allowed:
        return []

    vehicles = (
        Vehicle.objects.filter(company_id=company_id, status=VehicleStatus.AVAILABLE)
        .select_related("risk_tier")
        .order_by("current_km")
    )

    results: list[dict] = []
    for vehicle in vehicles:
        tier = infer_vehicle_tier(vehicle)
        if tier not in allowed:
            continue
        profile = resolve_sipp(vehicle.brand, vehicle.model, vehicle.sipp_code or None)
        results.append(
            {
                "vehicle_id": vehicle.pk,
                "plate_number": vehicle.plate_number,
                "brand": vehicle.brand,
                "model": vehicle.model,
                "tier": tier,
                "segment_label": profile.segment_label,
                "sipp_code": profile.code,
                "reason": f"Risk {level.value} → {tier} segment uygun",
            }
        )
        if len(results) >= limit:
            break

    return results
