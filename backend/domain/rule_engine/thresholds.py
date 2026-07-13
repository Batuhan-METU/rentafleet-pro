"""Risk seviyesi eşikleri — magic number yok."""

from __future__ import annotations

from backend.domain.shared.enums import RiskLevel

RISK_SCORE_MIN = 0
RISK_SCORE_MAX = 100
RISK_BLOCK_THRESHOLD = 81

RISK_LEVEL_BANDS: tuple[tuple[int, int, RiskLevel], ...] = (
    (0, 20, RiskLevel.VERY_LOW),
    (21, 40, RiskLevel.LOW),
    (41, 60, RiskLevel.MEDIUM),
    (61, 80, RiskLevel.HIGH),
    (81, 100, RiskLevel.VERY_HIGH),
)


def score_to_risk_level(score: int) -> RiskLevel:
    clamped = max(RISK_SCORE_MIN, min(RISK_SCORE_MAX, score))
    for low, high, level in RISK_LEVEL_BANDS:
        if low <= clamped <= high:
            return level
    return RiskLevel.VERY_HIGH