"""Paylaşılan risk değerlendirme çekirdeği."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.domain.deposit.engine import calculate_deposit
from backend.domain.eligibility.engine import recommend_vehicles
from backend.domain.risk.engine import RiskEngine
from backend.domain.rule_engine.audit import engine_result_to_audit_dict
from backend.domain.shared.types import CustomerSnapshot, EngineResult
from backend.apps.customer_profiles.models import Driver


RISK_LEVEL_LABELS = {
    "VERY_LOW": "Çok Düşük",
    "LOW": "Düşük",
    "MEDIUM": "Orta",
    "HIGH": "Yüksek",
    "VERY_HIGH": "Çok Yüksek",
}


@dataclass(frozen=True)
class RiskEvaluationBundle:
    risk_result: EngineResult
    audit: dict[str, Any]
    vehicles: tuple[dict[str, Any], ...]
    deposit: str | None
    approved: bool
    risk_level_label: str
    factors: tuple[dict[str, Any], ...]


def evaluate_customer_risk(
    driver: Driver,
    snapshot: CustomerSnapshot,
    *,
    company_id: int,
) -> RiskEvaluationBundle:
    """Risk motoru + uygunluk + depozito hesabını tek noktada çalıştırır."""
    resolved_company_id = company_id or driver.company_id
    engine = RiskEngine(company_id=resolved_company_id)
    risk_result = engine.evaluate(snapshot)
    audit = engine_result_to_audit_dict(risk_result)

    vehicles: list[dict[str, Any]] = []
    deposit = None
    if risk_result.approved and risk_result.level:
        vehicles = recommend_vehicles(driver.company_id, risk_result.level)
        deposit_val = calculate_deposit(
            risk_result.level,
            vip_tier=snapshot.vip_tier,
            customer_score=driver.current_customer_score,
            is_first_rental=snapshot.is_first_rental,
        )
        deposit = str(deposit_val) if deposit_val is not None else None

    level = risk_result.level or ""
    factors = tuple(
        {
            "code": outcome.code,
            "points": outcome.points,
            "message": outcome.message,
        }
        for outcome in risk_result.outcomes
        if outcome.effect.value == "ADD_SCORE"
    )

    return RiskEvaluationBundle(
        risk_result=risk_result,
        audit=audit,
        vehicles=tuple(vehicles),
        deposit=deposit,
        approved=risk_result.approved and bool(vehicles),
        risk_level_label=RISK_LEVEL_LABELS.get(level, level or "—"),
        factors=factors,
    )