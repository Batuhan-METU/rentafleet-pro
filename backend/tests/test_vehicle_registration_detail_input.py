"""Araç ekleme sihirbazının "Ruhsat Bilgileri" vb. adımlarından gelen iç içe
``registration_detail`` verisinin gerçek ``VehicleRegistrationDetail``
kaydına yazıldığını doğrular (FYS ruhsat-tipi araç ekleme sihirbazı)."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.companies.models import Company
from backend.apps.vehicles.models import Vehicle, VehicleRegistrationDetail

pytestmark = pytest.mark.django_db


def test_create_vehicle_with_registration_detail_creates_real_record(
    client: APIClient,
) -> None:
    payload = {
        "plate_number": "34REG001",
        "brand": "Renault",
        "model": "Clio",
        "production_year": 2024,
        "registration_detail": {
            "registration_serial_no": "AB123456",
            "registration_province": "İstanbul",
            "registration_district": "Kadıköy",
            "seat_count": 5,
            "owner_first_name": "Ahmet",
            "owner_surname_or_title": "Yılmaz",
        },
    }

    response = client.post("/api/vehicles/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED, response.data
    vehicle = Vehicle.objects.get(plate_number="34REG001")
    detail = VehicleRegistrationDetail.objects.get(vehicle=vehicle)
    assert detail.registration_serial_no == "AB123456"
    assert detail.seat_count == 5
    assert response.data["registration_detail"]["owner_first_name"] == "Ahmet"


def test_create_vehicle_without_registration_detail_leaves_it_unset(
    client: APIClient,
) -> None:
    payload = {
        "plate_number": "34REG002",
        "brand": "Renault",
        "model": "Clio",
        "production_year": 2024,
    }

    response = client.post("/api/vehicles/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED, response.data
    vehicle = Vehicle.objects.get(plate_number="34REG002")
    assert not VehicleRegistrationDetail.objects.filter(vehicle=vehicle).exists()
    assert response.data["registration_detail"] is None


def test_update_vehicle_registration_detail_upserts_single_row(
    client: APIClient, company: Company
) -> None:
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34REG003",
        brand="Renault",
        model="Clio",
        production_year=2024,
    )
    VehicleRegistrationDetail.objects.create(vehicle=vehicle, seat_count=4)

    response = client.patch(
        f"/api/vehicles/{vehicle.pk}/",
        {"registration_detail": {"seat_count": 5, "vehicle_class": "M1"}},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK, response.data
    assert VehicleRegistrationDetail.objects.filter(vehicle=vehicle).count() == 1
    detail = VehicleRegistrationDetail.objects.get(vehicle=vehicle)
    assert detail.seat_count == 5
    assert detail.vehicle_class == "M1"
