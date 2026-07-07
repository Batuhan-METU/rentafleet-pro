"""Genel kural değerlendirici."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.domain.shared.enums import RuleEffect
from backend.domain.shared.types import CustomerSnapshot, EngineResult, RuleOutcome


@dataclass(frozen=True)
class RuleDefinitionData:
    code: str
    priority: int
    effect: RuleEffect
    points: int
    message: str
    predicate: Callable[[CustomerSnapshot], bool]


class RuleEngine:
    """Sıralı kural listesini değerlendirir."""

    def __init__(self, engine_name: str, rules: list[RuleDefinitionData]) -> None:
        self._engine_name = engine_name
        self._rules = sorted(rules, key=lambda r: r.priority)

    def evaluate(self, customer: CustomerSnapshot) -> EngineResult:
        outcomes: list[RuleOutcome] = []
        blockers: list[str] = []
        warnings: list[str] = []
        score = 0

        for rule in self._rules:
            if not rule.predicate(customer):
                continue
            outcomes.append(
                RuleOutcome(
                    code=rule.code,
                    effect=rule.effect,
                    points=rule.points,
                    message=rule.message,
                )
            )
            if rule.effect == RuleEffect.ADD_SCORE:
                score += rule.points
            elif rule.effect == RuleEffect.BLOCK:
                blockers.append(rule.message)
            elif rule.effect == RuleEffect.WARN:
                warnings.append(rule.message)

        return EngineResult(
            engine=self._engine_name,
            score=score,
            level=None,
            outcomes=tuple(outcomes),
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )

    def to_audit_dict(self, result: EngineResult) -> dict[str, Any]:
        return {
            "engine": result.engine,
            "score": result.score,
            "level": result.level,
            "blockers": list(result.blockers),
            "warnings": list(result.warnings),
            "outcomes": [
                {
                    "code": o.code,
                    "effect": o.effect.value,
                    "points": o.points,
                    "message": o.message,
                }
                for o in result.outcomes
            ],
        }
