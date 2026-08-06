"""Araç ekleme sihirbazının "Giderler → Operasyon" bölümünden gelen iç içe
``operating_expenses`` verisinin gerçek ``VehicleExpense`` kayıtlarına
yazıldığını doğrular — bu, operating_expense_service'in (§3.5) TEK veri
kaynağıdır; ``Vehicle`` üzerindeki eski tahmini alanlar (ör.
``estimated_monthly_maintenance``) maliyet motoruna hiç bağlı değildir."""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import VehicleExpense
from backend.apps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db


def test_create_vehicle_with_operating_expenses_creates_real_records(
    client: APIClient,
) -> None:
    payload = {
        "plate_number": "34OPX001",
        "brand": "Renault",
        "model": "Clio",
        "production_year": 2024,
        "operating_expenses": [
            {
                "category": "VEHICLE_MAINTENANCE",
                "amount": "5000.00",
                "expense_date": "2026-01-15",
                "odometer_km": 42000,
            },
            {"category": "SEASONAL_TIRE_CHANGE", "amount": "3200.00", "expense_date": "2026-02-01"},
        ],
    }

    response = client.post("/api/vehicles/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED, response.data
    vehicle = Vehicle.objects.get(plate_number="34OPX001")
    expenses = VehicleExpense.objects.filter(vehicle=vehicle)
    assert expenses.count() == 2
    assert set(expenses.values_list("category", flat=True)) == {"VEHICLE_MAINTENANCE", "SEASONAL_TIRE_CHANGE"}
    assert len(response.data["operating_expenses"]) == 2


def test_update_vehicle_operating_expenses_appends_not_replaces(
    client: APIClient, company: Company
) -> None:
    """Sigorta poliçelerinin aksine, gider kayıtları tip başına tek satır
    değildir — her yeni gönderim MEVCUT kayıtların yerine geçmez, üstüne
    eklenir (bir aracın onlarca ayrı bakım kaydı olabilir)."""
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34OPX002",
        brand="Renault",
        model="Clio",
        production_year=2024,
    )
    VehicleExpense.objects.create(
        vehicle=vehicle, category="SEASONAL_TIRE_CHANGE", amount="1000.00", expense_date="2025-01-01"
    )

    response = client.patch(
        f"/api/vehicles/{vehicle.pk}/",
        {
            "operating_expenses": [
                {
                    "category": "VEHICLE_MAINTENANCE",
                    "amount": "2500.00",
                    "expense_date": "2026-03-01",
                    "odometer_km": 30000,
                },
            ]
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK, response.data
    assert VehicleExpense.objects.filter(vehicle=vehicle).count() == 2


def test_vehicle_maintenance_expense_requires_odometer_km(client: APIClient) -> None:
    """Bakım Merkezi'nin km boyutu bu veriye bağlı — km'siz bir "Araç Bakım"
    kaydı kalıcı olarak "bilinmiyor"a düşer, bu yüzden zorunlu tutulur."""
    payload = {
        "plate_number": "34OPX004",
        "brand": "Renault",
        "model": "Clio",
        "production_year": 2024,
        "operating_expenses": [
            {"category": "VEHICLE_MAINTENANCE", "amount": "5000.00", "expense_date": "2026-01-15"},
        ],
    }

    response = client.post("/api/vehicles/", payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Vehicle.objects.filter(plate_number="34OPX004").exists()


def test_operating_expense_optional_income_fields_persist(client: APIClient) -> None:
    """Bir gidere bağlı geri kazanım/tahsilat (ör. sigorta tazminatı) —
    "Operasyon Gider Kırılımı" ekranındaki kategori bazlı Gelir/Fark bu
    alanlardan hesaplanır."""
    payload = {
        "plate_number": "34OPX005",
        "brand": "Renault",
        "model": "Clio",
        "production_year": 2024,
        "operating_expenses": [
            {
                "category": "VEHICLE_DAMAGE_REPAIR",
                "amount": "8000.00",
                "expense_date": "2026-01-15",
                "income_amount": "6000.00",
                "income_source": "Sigorta Tazminatı",
            },
            {"category": "STANDARD_WASHING", "amount": "500.00", "expense_date": "2026-01-20"},
        ],
    }

    response = client.post("/api/vehicles/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED, response.data
    vehicle = Vehicle.objects.get(plate_number="34OPX005")
    damage_expense = VehicleExpense.objects.get(vehicle=vehicle, category="VEHICLE_DAMAGE_REPAIR")
    assert damage_expense.income_amount == Decimal("6000.00")
    assert damage_expense.income_source == "Sigorta Tazminatı"

    washing_expense = VehicleExpense.objects.get(vehicle=vehicle, category="STANDARD_WASHING")
    assert washing_expense.income_amount is None
    assert washing_expense.income_source == ""


def test_create_vehicle_without_operating_expenses_leaves_none(client: APIClient) -> None:
    payload = {
        "plate_number": "34OPX003",
        "brand": "Renault",
        "model": "Clio",
        "production_year": 2024,
    }

    response = client.post("/api/vehicles/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED, response.data
    vehicle = Vehicle.objects.get(plate_number="34OPX003")
    assert not VehicleExpense.objects.filter(vehicle=vehicle).exists()
    assert response.data["operating_expenses"] == []
