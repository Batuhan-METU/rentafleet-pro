"""Depozito hesaplama motoru testleri.

Depozito, aracın alım fiyatının değil KİRALAMA FİYATININ (fiyatlandırma
ekranında anlaşılan tutar) risk seviyesine göre bir yüzdesidir
(VERY_LOW %10, LOW %15, MEDIUM %20, HIGH %30).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.domain.deposit.engine import (
    calculate_deposit,
    deposit_percent_for_risk,
    effective_deposit_percent,
)

RENTAL_PRICE = Decimal("10000")


def test_very_high_risk_has_no_deposit_rental_blocked():
    assert calculate_deposit("VERY_HIGH", RENTAL_PRICE) is None


@pytest.mark.parametrize(
    "risk_level,expected",
    [
        ("VERY_LOW", Decimal("1000.00")),
        ("LOW", Decimal("1500.00")),
        ("MEDIUM", Decimal("2000.00")),
        ("HIGH", Decimal("3000.00")),
    ],
)
def test_deposit_percent_scales_with_rental_price(risk_level, expected):
    assert calculate_deposit(risk_level, RENTAL_PRICE) == expected


def test_deposit_amount_differs_across_rental_prices_for_same_risk_level():
    cheap = calculate_deposit("HIGH", Decimal("5000"))
    expensive = calculate_deposit("HIGH", Decimal("50000"))
    assert cheap == Decimal("1500.00")
    assert expensive == Decimal("15000.00")
    assert cheap != expensive


def test_unknown_risk_level_returns_none():
    assert calculate_deposit("NOT_A_LEVEL", RENTAL_PRICE) is None


def test_deposit_percent_for_risk_helper():
    assert deposit_percent_for_risk("VERY_LOW") == Decimal("0.10")
    assert deposit_percent_for_risk("HIGH") == Decimal("0.30")
    assert deposit_percent_for_risk("VERY_HIGH") is None
    assert deposit_percent_for_risk("NOT_A_LEVEL") is None


def test_vip_tier_applies_30_percent_discount():
    assert calculate_deposit("HIGH", RENTAL_PRICE, vip_tier="GOLD") == Decimal("2100.00")


def test_high_customer_score_applies_20_percent_discount():
    assert calculate_deposit("HIGH", RENTAL_PRICE, customer_score=85) == Decimal("2400.00")


def test_vip_and_high_score_discounts_stack_multiplicatively():
    # %30 * 0.70 (VIP) * 0.80 (yüksek skor) = %16.8 -> 10000 * 0.168 = 1680
    assert calculate_deposit(
        "HIGH", RENTAL_PRICE, vip_tier="PLATINUM", customer_score=90
    ) == Decimal("1680.00")


def test_first_rental_surcharge_applies_only_to_medium_and_high():
    assert calculate_deposit("MEDIUM", RENTAL_PRICE, is_first_rental=True) == Decimal("2500.00")
    assert calculate_deposit("HIGH", RENTAL_PRICE, is_first_rental=True) == Decimal("3750.00")
    # VERY_LOW/LOW ilk kiralama sürşarjından etkilenmez.
    assert calculate_deposit("LOW", RENTAL_PRICE, is_first_rental=True) == Decimal("1500.00")


def test_first_rental_surcharge_and_vip_discount_combine():
    # %20 * 0.70 (VIP) * 1.25 (ilk kiralama) = %17.5 -> 10000 * 0.175 = 1750
    assert calculate_deposit(
        "MEDIUM", RENTAL_PRICE, vip_tier="SILVER", is_first_rental=True
    ) == Decimal("1750.00")


def test_effective_deposit_percent_has_no_rental_price_dependency():
    # Oran, kiralama fiyatı bilinmeden de (örn. genel sürücü risk ekranında) hesaplanabilir.
    assert effective_deposit_percent("VERY_LOW") == Decimal("0.1000")
    assert effective_deposit_percent("HIGH", vip_tier="GOLD") == Decimal("0.2100")
    assert effective_deposit_percent("VERY_HIGH") is None
