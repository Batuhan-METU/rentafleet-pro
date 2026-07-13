"""Sürücü risk değerlendirmesi — kiralama başvurusu olmadan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from backend.application.customer.snapshots import build_customer_snapshot, ensure_customer_profiles
from backend.application.driver.persist_risk import persist_driver_risk_result
from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.evaluation import evaluate_customer_risk
from backend.apps.risk_checks.models import CustomerRiskSnapshot


@dataclass(frozen=True)
class DriverEvaluationResult:
    risk_score: int | None
    risk_level: str | None
    risk_level_label: str
    approved: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    factors: tuple[dict[str, Any], ...]
    eligible_vehicles: tuple[dict[str, Any], ...]
    deposit_amount: str | None


class DriverEvaluationService:
    @transaction.atomic
    def evaluate(self, driver: Driver) -> DriverEvaluationResult:
        ensure_customer_profiles(driver)
        snapshot = build_customer_snapshot(driver)
        bundle = evaluate_customer_risk(driver, snapshot, company_id=driver.company_id)

        CustomerRiskSnapshot.objects.create(
            driver=driver,
            application=None,
            risk_score=bundle.risk_result.score or 0,
            risk_level=bundle.risk_result.level or "MEDIUM",
            factor_breakdown={
                "audit": bundle.audit,
                "eligible_vehicles": list(bundle.vehicles),
                "deposit_amount": bundle.deposit,
            },
        )

        persist_driver_risk_result(driver, bundle)

        level = bundle.risk_result.level or ""
        return DriverEvaluationResult(
            risk_score=bundle.risk_result.score,
            risk_level=level or None,
            risk_level_label=bundle.risk_level_label,
            approved=bundle.approved,
            blockers=bundle.risk_result.blockers,
            warnings=bundle.risk_result.warnings,
            factors=bundle.factors,
            eligible_vehicles=bundle.vehicles,
            deposit_amount=bundle.deposit,
        )

    def serialize(self, result: DriverEvaluationResult) -> dict[str, Any]:
        return {
            "skor": result.risk_score,
            "seviye": result.risk_level,
            "seviye_label": result.risk_level_label,
            "onaylandi": result.approved,
            "blokajlar": list(result.blockers),
            "uyarilar": list(result.warnings),
            "faktorler": list(result.factors),
            "depozito": result.deposit_amount,
        }
