"""Kiralama create/cancel/return işlemlerinin Django admin LogEntry denetim
izine düştüğünü doğrular (bkz. common/audit.py)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from rest_framework import status

from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import Rental
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


def _driver(company: Company) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Audit",
        last_name="Sürücü",
        national_id="77777777770",
        birth_date=date.today() - timedelta(days=365 * 30),
        phone="5557778899",
        license_number="A000111",
        city="Ankara",
    )


def _vehicle(company: Company, plate: str) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=plate,
        brand="Dacia",
        model="Sandero",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
    )


def test_creating_a_rental_writes_an_addition_log_entry(client, company):
    driver = _driver(company)
    vehicle = _vehicle(company, "34AUD001")
    payload = {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=4)).isoformat(),
    }

    response = client.post("/api/rentals/", payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    rental = Rental.objects.get(driver=driver)
    entry = LogEntry.objects.get(object_id=str(rental.pk), action_flag=ADDITION)
    assert "oluşturuldu" in entry.change_message.lower()


def test_cancelling_a_future_rental_writes_a_change_log_entry(client, company):
    driver = _driver(company)
    vehicle = _vehicle(company, "34AUD002")
    payload = {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=5)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=8)).isoformat(),
    }
    create_resp = client.post("/api/rentals/", payload, format="json")
    rental_id = create_resp.data["id"]

    response = client.post(f"/api/rentals/{rental_id}/cancel/")
    assert response.status_code == status.HTTP_200_OK

    entry = LogEntry.objects.get(object_id=str(rental_id), action_flag=CHANGE)
    assert "iptal edildi" in entry.change_message.lower()
