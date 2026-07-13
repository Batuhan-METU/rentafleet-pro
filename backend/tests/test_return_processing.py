"""Araç teslim alma — erken/geç/zamanında hesaplama ve kalıcı kayıt testleri."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from backend.application.rental.return_processing import process_vehicle_return
from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver
from backend.apps.floor_pricing.models import RentalIncome
from backend.apps.reservations.models import Rental, RentalStatus, ReturnStatus
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def company() -> Company:
    return Company.objects.create(name="test-tenant", tax_number="7770001111")


@pytest.fixture
def driver(company: Company) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Test",
        last_name="Sürücü",
        national_id="44444444440",
        birth_date=timezone.now().date().replace(year=timezone.now().year - 35),
        phone="5551234567",
        license_number="Y123456",
        city="Ankara",
    )


@pytest.fixture
def vehicle(company: Company) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number="34RET001",
        brand="Renault",
        model="Clio",
        production_year=2023,
        current_km=10000,
        status=VehicleStatus.RENTED,
    )


def _active_rental(driver: Driver, vehicle: Vehicle, *, days: int = 10, quoted_total=Decimal("10000")) -> Rental:
    started_at = timezone.now() - timedelta(days=2)
    ended_at = started_at + timedelta(days=days)
    return Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        start_km=vehicle.current_km,
        quoted_total=quoted_total,
    )


def test_early_return_refunds_unused_days_and_frees_vehicle(driver, vehicle):
    rental = _active_rental(driver, vehicle, days=10, quoted_total=Decimal("10000"))
    actual_return_at = rental.ended_at - timedelta(days=3)

    settlement = process_vehicle_return(rental, actual_return_at, "erken teslim testi")

    assert settlement.return_status == ReturnStatus.EARLY
    assert settlement.unused_days == 3
    # Günlük ücret = 10000/10 = 1000; 3 gün iade = -3000
    assert settlement.price_difference == Decimal("-3000.00")

    rental.refresh_from_db()
    vehicle.refresh_from_db()
    assert rental.status == RentalStatus.COMPLETED
    assert rental.return_status == ReturnStatus.EARLY
    assert rental.price_difference == Decimal("-3000.00")
    assert rental.actual_return_at == actual_return_at
    assert vehicle.status == VehicleStatus.AVAILABLE

    income = RentalIncome.objects.get(rental=rental)
    assert income.base_amount == Decimal("-3000.00")
    assert income.total_income == Decimal("-3000.00")


def test_late_return_charges_extra_day_with_penalty(driver, vehicle):
    rental = _active_rental(driver, vehicle, days=5, quoted_total=Decimal("5000"))
    actual_return_at = rental.ended_at + timedelta(days=1)

    settlement = process_vehicle_return(rental, actual_return_at, "geç teslim testi")

    assert settlement.return_status == ReturnStatus.LATE
    # Günlük ücret = 5000/5 = 1000; 1 gün aşım × 1.25 ceza katsayısı = 1250
    assert settlement.price_difference == Decimal("1250.00")

    rental.refresh_from_db()
    vehicle.refresh_from_db()
    assert rental.status == RentalStatus.COMPLETED
    assert rental.return_status == ReturnStatus.LATE
    assert rental.price_difference == Decimal("1250.00")
    assert vehicle.status == VehicleStatus.AVAILABLE

    income = RentalIncome.objects.get(rental=rental)
    assert income.late_fee == Decimal("1250.00")
    assert income.total_income == Decimal("1250.00")


def test_on_time_within_grace_period_has_no_charge(driver, vehicle):
    rental = _active_rental(driver, vehicle, days=5, quoted_total=Decimal("5000"))
    actual_return_at = rental.ended_at + timedelta(hours=1)  # 2 saatlik tolerans içinde

    settlement = process_vehicle_return(rental, actual_return_at)

    assert settlement.return_status == ReturnStatus.ON_TIME
    assert settlement.price_difference == Decimal("0")
    assert not RentalIncome.objects.filter(rental=rental).exists()

    rental.refresh_from_db()
    assert rental.status == RentalStatus.COMPLETED
    assert rental.return_status == ReturnStatus.ON_TIME


def test_preview_does_not_mutate_anything(driver, vehicle):
    rental = _active_rental(driver, vehicle, days=10, quoted_total=Decimal("10000"))
    actual_return_at = rental.ended_at - timedelta(days=3)

    settlement = process_vehicle_return(rental, actual_return_at, preview=True)

    assert settlement.return_status == ReturnStatus.EARLY
    assert settlement.price_difference == Decimal("-3000.00")

    rental.refresh_from_db()
    vehicle.refresh_from_db()
    assert rental.status == RentalStatus.ACTIVE
    assert rental.actual_return_at is None
    assert vehicle.status == VehicleStatus.RENTED
    assert not RentalIncome.objects.filter(rental=rental).exists()
