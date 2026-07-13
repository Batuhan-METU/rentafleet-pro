"""POST /api/rentals/<pk>/return/ — uçtan uca view testi + sıfır çakışma kanıtı."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.companies.models import Company, CustomUser, UserRole
from backend.apps.customer_profiles.models import Driver
from backend.apps.reservations.models import Rental, RentalStatus, ReturnStatus
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def company() -> Company:
    return Company.objects.create(name="test-tenant", tax_number="8880001111")


@pytest.fixture
def manager(company: Company) -> CustomUser:
    return CustomUser.objects.create_user(
        username="test_mudur_return",
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
        first_name="Temiz",
        last_name="Sürücü",
        national_id="55555555550",
        birth_date=date.today() - timedelta(days=365 * 35),
        phone="5559998877",
        license_number="Z000111",
        city="Ankara",
    )


@pytest.fixture
def vehicle(company: Company) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number="34VG010",
        brand="Dacia",
        model="Duster",
        production_year=2023,
        current_km=8000,
        status=VehicleStatus.RENTED,
    )


def test_return_view_early_then_zero_conflict_on_rebooking(client, driver, vehicle):
    from django.utils import timezone

    started_at = timezone.now() - timedelta(days=2)
    ended_at = started_at + timedelta(days=10)
    rental = Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        start_km=vehicle.current_km,
        quoted_total=Decimal("10000"),
    )

    actual_return_at = ended_at - timedelta(days=3)

    preview_resp = client.post(
        f"/api/rentals/{rental.pk}/return/",
        {"actual_return_at": actual_return_at.isoformat(), "preview": True},
        format="json",
    )
    assert preview_resp.status_code == status.HTTP_200_OK
    assert preview_resp.data["durum"] == ReturnStatus.EARLY
    rental.refresh_from_db()
    assert rental.status == RentalStatus.ACTIVE  # preview hiçbir şeyi değiştirmedi

    commit_resp = client.post(
        f"/api/rentals/{rental.pk}/return/",
        {"actual_return_at": actual_return_at.isoformat(), "notes": "erken teslim"},
        format="json",
    )
    assert commit_resp.status_code == status.HTTP_200_OK
    assert commit_resp.data["durum"] == ReturnStatus.EARLY
    assert commit_resp.data["fark_tutari"] == "-3000.00"

    vehicle.refresh_from_db()
    assert vehicle.status == VehicleStatus.AVAILABLE

    # Sıfır çakışma: aynı araç için, orijinal (artık kapanmış) rezervasyonla
    # tarihsel olarak çakışan yeni bir rezervasyon denemesi başarılı olmalı —
    # çünkü eski kayıt artık ACTIVE değil, çakışma kontrolleri onu görmez.
    new_payload = {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=4)).isoformat(),
    }
    rebooking_resp = client.post("/api/rentals/", new_payload, format="json")
    assert rebooking_resp.status_code == status.HTTP_201_CREATED, rebooking_resp.data


def test_return_view_rejects_already_completed_rental(client, driver, vehicle):
    from django.utils import timezone

    started_at = timezone.now() - timedelta(days=10)
    ended_at = started_at + timedelta(days=5)
    rental = Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.COMPLETED,
        started_at=started_at,
        ended_at=ended_at,
        start_km=vehicle.current_km,
    )

    resp = client.post(
        f"/api/rentals/{rental.pk}/return/",
        {"actual_return_at": timezone.now().isoformat()},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
