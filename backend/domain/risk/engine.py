"""Risk skoru motoru."""

from __future__ import annotations

from backend.domain.rule_engine.engine import RuleEngine
from backend.domain.rule_engine.thresholds import (
    RISK_BLOCK_THRESHOLD,
    RISK_SCORE_MAX,
    RISK_SCORE_MIN,
    score_to_risk_level,
)
from backend.domain.risk.rule_loader import build_risk_engine
from backend.domain.shared.enums import RiskLevel
from backend.domain.shared.types import CustomerSnapshot, EngineResult


class RiskEngine:
    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        *,
        company_id: int | None = None,
    ) -> None:
        self._engine = rule_engine or build_risk_engine(company_id)

    def evaluate(self, customer: CustomerSnapshot) -> EngineResult:
        base = self._engine.evaluate(customer)
        raw_score = base.score or 0
        clamped = max(RISK_SCORE_MIN, min(RISK_SCORE_MAX, raw_score))
        level = score_to_risk_level(clamped)

        blockers = list(base.blockers)
        if level == RiskLevel.VERY_HIGH and clamped >= RISK_BLOCK_THRESHOLD:
            blockers.append("Risk skoru çok yüksek — araç kiralanamaz.")

        return EngineResult(
            engine=base.engine,
            score=clamped,
            level=level.value,
            outcomes=base.outcomes,
            blockers=tuple(blockers),
            warnings=base.warnings,
            metadata={"block_threshold": RISK_BLOCK_THRESHOLD},
        )
