"""Araç oluşturma/güncelleme formundan gelen iç içe ``insurance_policies``
verisinin gerçek ``InsurancePolicy`` kayıtlarına yazıldığını doğrular —
"Poliçe Ekle" ekranı kaldırılıp bu akışa taşındığı için bu, poliçe
girişinin artık TEK yolu.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import InsurancePolicy
from backend.apps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db


def test_create_vehicle_with_insurance_policies_creates_real_records(
    client: APIClient,
) -> None:
    payload = {
        "plate_number": "34POL001",
        "brand": "Renault",
        "model": "Clio",
        "production_year": 2024,
        "insurance_policies": [
            {
                "policy_type": "LIABILITY",
                "amount": "12000.00",
                "start_date": "2026-01-01",
                "end_date": "2027-01-01",
            },
            {
                "policy_type": "COMPREHENSIVE",
                "amount": "45000.00",
                "start_date": "2026-01-01",
                "end_date": "2027-01-01",
            },
        ],
    }

    response = client.post("/api/vehicles/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED, response.data
    vehicle = Vehicle.objects.get(plate_number="34POL001")
    policies = InsurancePolicy.objects.filter(vehicle=vehicle)
    assert policies.count() == 2
    assert set(policies.values_list("policy_type", flat=True)) == {"LIABILITY", "COMPREHENSIVE"}
    assert response.data["insurance_policies"][0]["amount"]


def test_update_vehicle_insurance_policy_overwrites_existing_by_type(
    client: APIClient, company: Company
) -> None:
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34POL002",
        brand="Renault",
        model="Clio",
        production_year=2024,
    )
    InsurancePolicy.objects.create(
        vehicle=vehicle,
        policy_type="LIABILITY",
        amount=Decimal("10000"),
        start_date=date(2025, 1, 1),
        end_date=date(2026, 1, 1),
    )

    response = client.patch(
        f"/api/vehicles/{vehicle.pk}/",
        {
            "insurance_policies": [
                {
                    "policy_type": "LIABILITY",
                    "amount": "15000.00",
                    "start_date": "2026-01-01",
                    "end_date": "2027-01-01",
                }
            ]
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK, response.data
    policies = InsurancePolicy.objects.filter(vehicle=vehicle, policy_type="LIABILITY")
    assert policies.count() == 1
    policy = policies.first()
    assert policy is not None
    assert policy.amount == Decimal("15000.00")
