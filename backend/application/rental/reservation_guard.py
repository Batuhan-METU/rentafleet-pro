"""Rezervasyon atamasından önce risk + araç uygunluk kapısı."""

from __future__ import annotations

from datetime import datetime

from rest_framework.exceptions import ValidationError

from backend.application.rental.driver_eligibility import assert_driver_eligible_for_vehicle
from backend.application.rental.evaluate_application import RentalApplicationService
from backend.apps.companies.models import Company, CustomUser
from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import DecisionStep, RentalApplication, RentalDecisionLog, RuleEngineType
from backend.apps.vehicles.models import Vehicle


def enforce_risk_and_eligibility(
    *,
    company: Company,
    driver: Driver,
    vehicle: Vehicle,
    created_by: CustomUser | None,
    requested_pickup_at: datetime,
    requested_return_at: datetime,
) -> RentalApplication:
    """Risk + araç uygunluk kontrolünü çalıştırır; onaylanırsa ``RentalApplication``'ı döner."""
    service = RentalApplicationService()
    application = service.create_application(
        company=company,
        driver=driver,
        created_by=created_by,
        requested_pickup_at=requested_pickup_at,
        requested_return_at=requested_return_at,
    )
    result = service.evaluate(application)

    if not result.approved:
        blockers = "; ".join(result.risk.blockers)
        if not blockers:
            blockers = "Risk değerlendirmesi onaylanmadı."
        raise ValidationError(
            {"error": f"Sürücü risk skoru yetersiz olduğu için rezervasyon onaylanamaz: {blockers}"}
        )

    eligible_vehicle_ids = {v["vehicle_id"] for v in result.vehicles}
    if vehicle.pk not in eligible_vehicle_ids:
        RentalDecisionLog.objects.create(
            application=application,
            step=DecisionStep.ELIGIBILITY,
            engine=RuleEngineType.ELIGIBILITY,
            input_snapshot={
                "attempted_vehicle_id": vehicle.pk,
                "risk_level": result.risk.level,
            },
            output_snapshot={"eligible_vehicle_ids": sorted(eligible_vehicle_ids)},
            approved=False,
            rule_version="1.0.0",
        )
        raise ValidationError(
            {"error": "Seçilen araç, sürücünün risk seviyesine uygun segmentte değil."}
        )

    assert_driver_eligible_for_vehicle(driver, vehicle)

    return application
