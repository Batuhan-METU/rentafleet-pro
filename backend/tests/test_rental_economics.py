"""Kiralama maliyet ekonomisi (rental_economics_service) — bellek içi Vehicle.

``build_vehicle_cost_card`` yalnızca ``vehicle`` alanlarını okur; satın alma
fiyatı doluyken hiçbir ilişkili tabloya gitmez, bu yüzden DB'ye kaydedilmemiş
bir ``Vehicle(...)`` nesnesiyle test edilebilir (django_db gerekmez).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.apps.companies.models import Company
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.pricing.rental_economics_service import (
    PLANNING_HORIZON_DAYS,
    build_vehicle_cost_card,
    rental_days_between,
)
from datetime import date


def _vehicle(**overrides) -> Vehicle:
    defaults = dict(
        plate_number="34TEST01",
        brand="Renault",
        model="Clio",
        production_year=2022,
        purchase_price=Decimal("730000"),
        initial_industrial_expense=Decimal("0"),
        annual_kasko_cost=Decimal("0"),
        annual_traffic_insurance_cost=Decimal("0"),
        annual_insurance_cost=Decimal("0"),
        annual_mtv_cost=Decimal("0"),
        estimated_monthly_maintenance=Decimal("0"),
        annual_inspection_cost=Decimal("0"),
    )
    defaults.update(overrides)
    return Vehicle(**defaults)


@pytest.mark.django_db
def test_no_purchase_price_means_no_cost_card():
    # purchase_price boşsa servis vehicle.financial_profile'a (DB) düşer.
    company = Company.objects.create(name="test-tenant", tax_number="1234567890")
    vehicle = _vehicle(purchase_price=None, company=company)
    vehicle.save()
    assert build_vehicle_cost_card(vehicle) is None


def test_daily_cost_is_annual_burden_over_365():
    vehicle = _vehicle(
        purchase_price=Decimal("730000"),
        initial_industrial_expense=Decimal("0"),
        annual_kasko_cost=Decimal("24000"),
        annual_traffic_insurance_cost=Decimal("12000"),
        annual_mtv_cost=Decimal("4800"),
        estimated_monthly_maintenance=Decimal("2500"),
        annual_inspection_cost=Decimal("1200"),
    )
    card = build_vehicle_cost_card(vehicle)

    assert card is not None
    monthly = (Decimal("36000") / 12) + (Decimal("4800") / 12) + (Decimal("1200") / 12) + Decimal("2500")
    annual_operating = monthly * 12
    annual_burden = Decimal("730000") + Decimal("0") + annual_operating
    expected_daily = round(float(annual_burden) / PLANNING_HORIZON_DAYS, 2)

    assert card.daily_cost == expected_daily
    assert card.estimated_fields == []


def test_missing_insurance_and_maintenance_fields_are_estimated():
    vehicle = _vehicle(
        purchase_price=Decimal("500000"),
        annual_kasko_cost=Decimal("0"),
        annual_traffic_insurance_cost=Decimal("0"),
        annual_insurance_cost=Decimal("0"),
        annual_mtv_cost=Decimal("0"),
        estimated_monthly_maintenance=Decimal("0"),
    )
    card = build_vehicle_cost_card(vehicle)

    assert card is not None
    # %4.5 sigorta + %1.2 MTV tahmini + varsayılan aylık bakım kullanılmalı.
    assert card.annual_insurance == round(500000 * 0.045, 2)
    assert card.annual_mtv == round(500000 * 0.012, 2)
    assert card.monthly_maintenance == 2500.0
    assert "annual_kasko_cost / annual_traffic_insurance_cost" in card.estimated_fields
    assert "annual_mtv_cost" in card.estimated_fields
    assert "estimated_monthly_maintenance" in card.estimated_fields


def test_explicit_kasko_and_traffic_beats_generic_insurance_field():
    vehicle = _vehicle(
        purchase_price=Decimal("500000"),
        annual_kasko_cost=Decimal("20000"),
        annual_traffic_insurance_cost=Decimal("8000"),
        annual_insurance_cost=Decimal("999999"),  # dolu olsa da kasko+trafik önceliklidir
    )
    card = build_vehicle_cost_card(vehicle)

    assert card.annual_insurance == 28000.0
    assert "annual_kasko_cost / annual_traffic_insurance_cost" not in card.estimated_fields


def test_rental_days_between_is_at_least_one():
    assert rental_days_between(date(2026, 7, 10), date(2026, 7, 10)) == 1
    assert rental_days_between(date(2026, 7, 10), date(2026, 7, 15)) == 5
