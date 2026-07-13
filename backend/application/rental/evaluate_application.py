"""Kiralama başvurusu use-case'leri."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction

from backend.application.customer.snapshots import build_customer_snapshot, ensure_customer_profiles
from backend.application.driver.persist_risk import persist_driver_risk_result
from backend.apps.customer_profiles.models import Driver
from backend.apps.reservations.choices import RentalStatus
from backend.apps.risk_checks.evaluation import evaluate_customer_risk
from backend.apps.risk_checks.models import (
    CustomerRiskSnapshot,
    DecisionStep,
    RentalApplication,
    RentalApplicationStatus,
    RentalDecisionLog,
    RuleEngineType,
)
from backend.apps.companies.models import (
    Company,
    CustomUser,
)

from backend.domain.shared.types import EvaluateRentalResult


class RentalApplicationService:
    @transaction.atomic
    def create_application(
        self,
        *,
        company: Company,
        driver: Driver,
        created_by: CustomUser | None,
        requested_pickup_at: datetime | None = None,
        requested_return_at: datetime | None = None,
    ) -> RentalApplication:
        ensure_customer_profiles(driver)
        completed = driver.rentals.filter(status=RentalStatus.COMPLETED).count()
        application = RentalApplication.objects.create(
            company=company,
            driver=driver,
            created_by=created_by,
            is_first_rental=completed == 0,
            requested_pickup_at=requested_pickup_at,
            requested_return_at=requested_return_at,
            status=RentalApplicationStatus.DRAFT,
        )
        RentalDecisionLog.objects.create(
            application=application,
            step=DecisionStep.INTAKE,
            engine="",
            input_snapshot={"driver_id": driver.pk},
            output_snapshot={"status": application.status},
            approved=True,
            rule_version="1.0.0",
        )
        return application

    @transaction.atomic
    def evaluate(self, application: RentalApplication) -> EvaluateRentalResult:
        driver = application.driver
        ensure_customer_profiles(driver)
        snapshot = build_customer_snapshot(driver, is_first_rental=application.is_first_rental)
        bundle = evaluate_customer_risk(
            driver,
            snapshot,
            company_id=application.company_id,
        )

        RentalDecisionLog.objects.create(
            application=application,
            step=DecisionStep.RISK,
            engine=RuleEngineType.RISK,
            input_snapshot={"customer_id": driver.pk},
            output_snapshot=bundle.audit,
            score=bundle.risk_result.score,
            risk_level=bundle.risk_result.level or "",
            approved=bundle.risk_result.approved,
            rule_version="1.0.0",
        )

        CustomerRiskSnapshot.objects.create(
            driver=driver,
            application=application,
            risk_score=bundle.risk_result.score or 0,
            risk_level=bundle.risk_result.level or "MEDIUM",
            factor_breakdown={
                "audit": bundle.audit,
                "eligible_vehicles": list(bundle.vehicles),
                "deposit_amount": bundle.deposit,
            },
        )

        persist_driver_risk_result(driver, bundle)

        application.risk_score = bundle.risk_result.score
        application.risk_level = bundle.risk_result.level or ""
        application.status = (
            RentalApplicationStatus.REJECTED
            if not bundle.approved
            else RentalApplicationStatus.EVALUATED
        )
        if not bundle.approved:
            blockers = bundle.risk_result.blockers
            if not blockers and not bundle.vehicles:
                blockers = ("Risk seviyesine uygun araç segmenti bulunamadı.",)
            application.rejection_reason = "; ".join(blockers)
        application.save(
            update_fields=["risk_score", "risk_level", "status", "rejection_reason", "updated_at"]
        )

        vehicles = list(bundle.vehicles)
        deposit = bundle.deposit
        if bundle.risk_result.approved and bundle.risk_result.level:
            application.deposit_amount = deposit
            application.save(update_fields=["deposit_amount", "updated_at"])

            RentalDecisionLog.objects.create(
                application=application,
                step=DecisionStep.ELIGIBILITY,
                engine=RuleEngineType.ELIGIBILITY,
                input_snapshot={"risk_level": bundle.risk_result.level},
                output_snapshot={"vehicles": vehicles},
                approved=bool(vehicles),
                rule_version="1.0.0",
            )

            if deposit is not None:
                RentalDecisionLog.objects.create(
                    application=application,
                    step=DecisionStep.DEPOSIT,
                    engine=RuleEngineType.DEPOSIT,
                    input_snapshot={"risk_level": bundle.risk_result.level},
                    output_snapshot={"deposit_amount": deposit},
                    approved=True,
                    rule_version="1.0.0",
                )

        return EvaluateRentalResult(
            application_id=application.pk,
            risk=bundle.risk_result,
            approved=bundle.approved,
            recommended_vehicle_ids=tuple(v["vehicle_id"] for v in vehicles),
            vehicles=tuple(vehicles),
            quote={"deposit_amount": deposit} if deposit is not None else None,
        )

    def serialize_evaluation(self, result: EvaluateRentalResult, application: RentalApplication) -> dict[str, Any]:
        vehicles = list(result.vehicles)

        return {
            "application_id": application.pk,
            "status": application.status,
            "decision": {
                "approved": result.approved,
                "risk": {
                    "score": result.risk.score,
                    "level": result.risk.level,
                    "blockers": list(result.risk.blockers),
                    "warnings": list(result.risk.warnings),
                    "factors": [
                        {
                            "code": o.code,
                            "points": o.points,
                            "message": o.message,
                        }
                        for o in result.risk.outcomes
                        if o.effect.value == "ADD_SCORE"
                    ],
                },
                "vehicles_recommended": vehicles,
                "deposit_amount": str(application.deposit_amount) if application.deposit_amount else None,
                "rejection_reason": application.rejection_reason,
            },
        }
