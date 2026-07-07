"""Kural motoru audit yardımcıları."""

from __future__ import annotations

from typing import Any

from backend.domain.shared.types import EngineResult


def engine_result_to_audit_dict(result: EngineResult) -> dict[str, Any]:
    return {
        "engine": result.engine,
        "score": result.score,
        "level": result.level,
        "blockers": list(result.blockers),
        "warnings": list(result.warnings),
        "outcomes": [
            {
                "code": outcome.code,
                "effect": outcome.effect.value,
                "points": outcome.points,
                "message": outcome.message,
            }
            for outcome in result.outcomes
        ],
    }
