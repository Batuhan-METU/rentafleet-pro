"""Depozito hesaplama motoru testleri."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.deposit.engine import calculate_deposit


def test_very_high_risk_has_no_deposit_rental_blocked():
    assert calculate_deposit("VERY_HIGH") is None


@pytest.mark.parametrize(
    "risk_level,expected",
    [
        ("VERY_LOW", Decimal("5000.00")),
        ("LOW", Decimal("5000.00")),
        ("MEDIUM", Decimal("10000.00")),
        ("HIGH", Decimal("20000.00")),
    ],
)
def test_base_deposit_by_risk_level(risk_level, expected):
    assert calculate_deposit(risk_level) == expected


def test_unknown_risk_level_returns_none():
    assert calculate_deposit("NOT_A_LEVEL") is None


def test_vip_tier_applies_30_percent_discount():
    assert calculate_deposit("HIGH", vip_tier="GOLD") == Decimal("14000.00")


def test_high_customer_score_applies_20_percent_discount():
    assert calculate_deposit("HIGH", customer_score=85) == Decimal("16000.00")


def test_vip_and_high_score_discounts_stack_multiplicatively():
    # 20000 * 0.70 (VIP) * 0.80 (yüksek skor) = 11200
    assert calculate_deposit("HIGH", vip_tier="PLATINUM", customer_score=90) == Decimal("11200.00")


def test_first_rental_surcharge_applies_only_to_medium_and_high():
    assert calculate_deposit("MEDIUM", is_first_rental=True) == Decimal("12500.00")
    assert calculate_deposit("HIGH", is_first_rental=True) == Decimal("25000.00")
    # VERY_LOW/LOW ilk kiralama sürşarjından etkilenmez.
    assert calculate_deposit("LOW", is_first_rental=True) == Decimal("5000.00")


def test_first_rental_surcharge_and_vip_discount_combine():
    # 10000 * 0.70 (VIP) * 1.25 (ilk kiralama) = 8750
    assert calculate_deposit(
        "MEDIUM", vip_tier="SILVER", is_first_rental=True
    ) == Decimal("8750.00")
