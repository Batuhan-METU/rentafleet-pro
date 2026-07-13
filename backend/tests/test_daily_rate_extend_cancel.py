"""Günlük fiyat, rezervasyon uzatma ve iptal/erken-teslim ayrımı testleri."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from backend.application.rental.return_processing import (
    extend_active_rental,
    process_vehicle_return,
)
from backend.apps.companies.models import Company, CustomUser, UserRole
from backend.apps.customer_profiles.models import Driver
from backend.apps.reservations.models import Rental, RentalStatus, ReturnStatus
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def company() -> Company:
    return Company.objects.create(name="test-tenant-dre", tax_number="9990001111")


@pytest.fixture
def manager(company: Company) -> CustomUser:
    return CustomUser.objects.create_user(
        username="test_mudur_dre",
        password="test-pass-123",
        company=company,
        role=UserRole.FLEET_MANAGER,
    )


@pytest.fixture
def client(manager: CustomUser) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=manager)
    return api_client


@pytest.fixture
def driver(company: Company) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Dre",
        last_name="Sürücü",
        national_id="66666666660",
        birth_date=date.today() - timedelta(days=365 * 35),
        phone="5551112233",
        license_number="D111222",
        city="Ankara",
    )


@pytest.fixture
def vehicle(company: Company) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number="34DRE001",
        brand="Fiat",
        model="Egea",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.RENTED,
    )


def _rental(
    driver: Driver,
    vehicle: Vehicle,
    *,
    days: int = 5,
    daily_rate=Decimal("4000"),
    status_=RentalStatus.ACTIVE,
    started_offset_days: int = 2,
) -> Rental:
    started_at = timezone.now() - timedelta(days=started_offset_days)
    ended_at = started_at + timedelta(days=days)
    return Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=status_,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=daily_rate,
    )


def test_daily_rate_used_directly_no_division(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("4000"))
    actual_return_at = rental.ended_at - timedelta(days=2)

    settlement = process_vehicle_return(rental, actual_return_at, "günlük fiyat testi")

    assert settlement.return_status == ReturnStatus.EARLY
    assert settlement.unused_days == 2
    assert settlement.price_difference == Decimal("-8000.00")


def test_extension_full_use_no_penalty(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("1000"))
    new_ended_at = rental.ended_at + timedelta(days=3)

    extend_active_rental(rental, new_ended_at)
    rental.refresh_from_db()
    assert rental.ended_at == new_ended_at
    assert rental.original_ended_at != new_ended_at

    settlement = process_vehicle_return(rental, new_ended_at)

    assert settlement.return_status == ReturnStatus.LATE
    assert settlement.price_difference == Decimal("3000.00")  # 3 gün × 1000, cezasız


def test_extension_plus_unplanned_overage_combines_charges(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("1000"))
    new_ended_at = rental.ended_at + timedelta(days=3)
    extend_active_rental(rental, new_ended_at)
    rental.refresh_from_db()

    actual_return_at = new_ended_at + timedelta(days=1)
    settlement = process_vehicle_return(rental, actual_return_at)

    assert settlement.return_status == ReturnStatus.LATE
    # Planlı: 3 gün × 1000 = 3000 (cezasız). Plansız aşım: 1 gün × 1000 × 1.25 = 1250.
    assert settlement.price_difference == Decimal("4250.00")


def test_extension_rejected_on_vehicle_conflict(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("1000"))
    original_ended_at = rental.ended_at

    other_driver = Driver.objects.create(
        company=vehicle.company,
        first_name="Diger",
        last_name="Surucu",
        national_id="77777777770",
        birth_date=date.today() - timedelta(days=365 * 30),
        phone="5553334455",
        license_number="D333444",
        city="Ankara",
    )
    Rental.objects.create(
        driver=other_driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=original_ended_at + timedelta(days=1),
        ended_at=original_ended_at + timedelta(days=6),
        original_ended_at=original_ended_at + timedelta(days=6),
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    with pytest.raises(ValidationError):
        extend_active_rental(rental, original_ended_at + timedelta(days=3))

    rental.refresh_from_db()
    assert rental.ended_at == original_ended_at


def test_future_reservation_cancel_has_no_price_difference(client, driver, vehicle):
    started_at = timezone.now() + timedelta(days=3)
    ended_at = started_at + timedelta(days=5)
    rental = Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )
    vehicle.status = VehicleStatus.AVAILABLE
    vehicle.save(update_fields=["status"])

    resp = client.post(f"/api/rentals/{rental.pk}/cancel/", format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["status"] == RentalStatus.CANCELLED
    assert resp.data.get("price_difference") in (None, "0.00")


def test_active_reservation_cancel_is_treated_as_early_return(client, driver, vehicle):
    started_at = timezone.now() - timedelta(days=2)
    ended_at = started_at + timedelta(days=10)
    rental = Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    resp = client.post(f"/api/rentals/{rental.pk}/cancel/", format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["durum"] == ReturnStatus.EARLY
    assert Decimal(resp.data["fark_tutari"]) < 0

    rental.refresh_from_db()
    assert rental.status == RentalStatus.COMPLETED
    assert rental.return_status == ReturnStatus.EARLY


def test_donem_filter_keeps_overdue_active_rental_in_aktif(client, driver, vehicle):
    started_at = timezone.now() - timedelta(days=10)
    ended_at = timezone.now() - timedelta(days=1)  # sözleşme tarihi geçmiş ama hâlâ ACTIVE
    Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    aktif_resp = client.get("/api/rentals/", {"donem": "AKTIF"}, format="json")
    assert aktif_resp.status_code == status.HTTP_200_OK
    assert aktif_resp.data["toplam"] == 1

    gecmis_resp = client.get("/api/rentals/", {"donem": "GECMIS"}, format="json")
    assert gecmis_resp.status_code == status.HTTP_200_OK
    assert gecmis_resp.data["toplam"] == 0
