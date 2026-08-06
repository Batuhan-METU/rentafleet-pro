"""Loan ↔ Vehicle tahsis API'si — /api/loans/<pk>/allocations/, /api/loan-allocations/<pk>/."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import Loan, LoanVehicleAllocation
from backend.apps.vehicles.models import Vehicle

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_company() -> Company:
    return Company.objects.create(name="rival-tenant", tax_number="7770002222")


@pytest.fixture
def loan(company: Company) -> Loan:
    return Loan.objects.create(
        company=company,
        lender_name="Test Bankası",
        principal_amount=Decimal("1000000"),
        monthly_interest_rate=Decimal("0.035"),
        term_months=36,
        start_date=date(2026, 1, 1),
    )


def _vehicle(company: Company, plate: str, purchase_price=Decimal("500000")) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=plate,
        brand="Renault",
        model="Clio",
        production_year=2024,
        purchase_price=purchase_price,
        fleet_entry_date=date(2026, 1, 1),
    )


def test_create_allocation_within_purchase_price(client: APIClient, company: Company, loan: Loan) -> None:
    vehicle = _vehicle(company, "34LOAN01")

    response = client.post(
        f"/api/loans/{loan.pk}/allocations/",
        {"vehicle": vehicle.pk, "financed_amount": "300000.00"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert LoanVehicleAllocation.objects.filter(loan=loan, vehicle=vehicle).exists()
    assert response.data["plate_number"] == "34LOAN01"


def test_allocation_cannot_exceed_purchase_price(client: APIClient, company: Company, loan: Loan) -> None:
    vehicle = _vehicle(company, "34LOAN02", purchase_price=Decimal("100000"))
    LoanVehicleAllocation.objects.create(loan=loan, vehicle=vehicle, financed_amount=Decimal("80000"))

    response = client.post(
        f"/api/loans/{loan.pk}/allocations/",
        {"vehicle": vehicle.pk, "financed_amount": "30000.00"},  # 80k + 30k > 100k
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "financed_amount" in response.data


def test_allocation_rejects_other_companys_vehicle(
    client: APIClient, other_company: Company, loan: Loan
) -> None:
    foreign_vehicle = _vehicle(other_company, "34RIVAL1")

    response = client.post(
        f"/api/loans/{loan.pk}/allocations/",
        {"vehicle": foreign_vehicle.pk, "financed_amount": "10000.00"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "vehicle" in response.data


def test_delete_allocation(client: APIClient, company: Company, loan: Loan) -> None:
    vehicle = _vehicle(company, "34LOAN03")
    allocation = LoanVehicleAllocation.objects.create(
        loan=loan, vehicle=vehicle, financed_amount=Decimal("200000")
    )

    response = client.delete(f"/api/loan-allocations/{allocation.pk}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not LoanVehicleAllocation.objects.filter(pk=allocation.pk).exists()


def test_list_allocations_scoped_to_loan(client: APIClient, company: Company, loan: Loan) -> None:
    vehicle = _vehicle(company, "34LOAN04")
    LoanVehicleAllocation.objects.create(loan=loan, vehicle=vehicle, financed_amount=Decimal("150000"))
    other_loan = Loan.objects.create(
        company=company,
        principal_amount=Decimal("500000"),
        monthly_interest_rate=Decimal("0.03"),
        term_months=12,
        start_date=date(2026, 1, 1),
    )
    other_vehicle = _vehicle(company, "34LOAN05")
    LoanVehicleAllocation.objects.create(
        loan=other_loan, vehicle=other_vehicle, financed_amount=Decimal("100000")
    )

    response = client.get(f"/api/loans/{loan.pk}/allocations/")

    assert response.status_code == status.HTTP_200_OK
    rows = response.data.get("results", response.data)
    plates = [row["plate_number"] for row in rows]
    assert plates == ["34LOAN04"]
