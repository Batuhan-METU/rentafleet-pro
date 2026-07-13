"""Depozito hesaplama motoru."""

from __future__ import annotations

from decimal import Decimal

from backend.domain.shared.enums import RiskLevel

DEPOSIT_BY_RISK: dict[RiskLevel, Decimal] = {
    RiskLevel.VERY_LOW: Decimal("5000"),
    RiskLevel.LOW: Decimal("5000"),
    RiskLevel.MEDIUM: Decimal("10000"),
    RiskLevel.HIGH: Decimal("20000"),
    RiskLevel.VERY_HIGH: Decimal("0"),
}

VIP_DEPOSIT_DISCOUNT = Decimal("0.30")
HIGH_CUSTOMER_SCORE_THRESHOLD = 80
CUSTOMER_SCORE_DEPOSIT_DISCOUNT = Decimal("0.20")
FIRST_RENTAL_SURCHARGE = Decimal("0.25")


def calculate_deposit(
    risk_level: str,
    *,
    vip_tier: str = "NONE",
    customer_score: int | None = None,
    is_first_rental: bool = False,
) -> Decimal | None:
    try:
        level = RiskLevel(risk_level)
    except ValueError:
        return None

    if level == RiskLevel.VERY_HIGH:
        return None

    base = DEPOSIT_BY_RISK[level]
    amount = base

    if vip_tier in {"SILVER", "GOLD", "PLATINUM"}:
        amount *= Decimal("1") - VIP_DEPOSIT_DISCOUNT

    if customer_score is not None and customer_score >= HIGH_CUSTOMER_SCORE_THRESHOLD:
        amount *= Decimal("1") - CUSTOMER_SCORE_DEPOSIT_DISCOUNT

    if is_first_rental and level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
        amount *= Decimal("1") + FIRST_RENTAL_SURCHARGE

    return amount.quantize(Decimal("0.01"))