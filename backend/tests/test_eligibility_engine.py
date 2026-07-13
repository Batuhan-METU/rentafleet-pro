"""Araç uygunluk motoru (recommend_vehicles) — gerçek DB kayıtlarıyla."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.apps.companies.models import Company
from backend.apps.vehicles.models import Vehicle, VehicleStatus
from backend.domain.eligibility.engine import recommend_vehicles

pytestmark = pytest.mark.django_db


@pytest.fixture
def company() -> Company:
    return Company.objects.create(name="test-tenant", tax_number="1234567890")


def _vehicle(company: Company, *, brand: str, plate: str, status=VehicleStatus.AVAILABLE, km=10000) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=plate,
        brand=brand,
        model="Model",
        production_year=2022,
        current_km=km,
        status=status,
        purchase_price=Decimal("500000"),
    )


def test_very_high_risk_gets_no_vehicles(company):
    _vehicle(company, brand="Dacia", plate="34AA001")
    assert recommend_vehicles(company.pk, "VERY_HIGH") == []


def test_high_risk_only_gets_economy_tier(company):
    _vehicle(company, brand="Mercedes", plate="34AA002")  # premium brand
    _vehicle(company, brand="Dacia", plate="34AA003")  # economy brand

    results = recommend_vehicles(company.pk, "HIGH")

    assert [r["plate_number"] for r in results] == ["34AA003"]
    assert results[0]["tier"] == "ECONOMY"


def test_very_low_risk_gets_all_tiers(company):
    _vehicle(company, brand="Mercedes", plate="34AA004")
    _vehicle(company, brand="Dacia", plate="34AA005")
    _vehicle(company, brand="Toyota", plate="34AA006")  # unknown -> STANDARD

    results = recommend_vehicles(company.pk, "VERY_LOW")

    assert {r["plate_number"] for r in results} == {"34AA004", "34AA005", "34AA006"}


def test_only_available_vehicles_are_recommended(company):
    _vehicle(company, brand="Dacia", plate="34AA007", status=VehicleStatus.RENTED)
    _vehicle(company, brand="Dacia", plate="34AA008", status=VehicleStatus.AVAILABLE)

    results = recommend_vehicles(company.pk, "HIGH")

    assert [r["plate_number"] for r in results] == ["34AA008"]


def test_vehicles_from_other_companies_are_never_recommended(company):
    other = Company.objects.create(name="other-tenant", tax_number="9999999999")
    _vehicle(other, brand="Dacia", plate="34AA009")

    assert recommend_vehicles(company.pk, "HIGH") == []


def test_invalid_risk_level_returns_empty_list(company):
    _vehicle(company, brand="Dacia", plate="34AA010")
    assert recommend_vehicles(company.pk, "NOT_A_LEVEL") == []


def test_result_limit_is_respected(company):
    for i in range(12):
        _vehicle(company, brand="Dacia", plate=f"34AA1{i:02d}", km=i)

    results = recommend_vehicles(company.pk, "VERY_LOW", limit=5)

    assert len(results) == 5
