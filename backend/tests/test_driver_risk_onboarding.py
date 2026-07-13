"""Sürücü kayıt anında otomatik risk skoru hesaplama testleri."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from backend.application.driver.evaluate_driver import DriverEvaluationService
from backend.application.rental.reservation_guard import enforce_risk_and_eligibility
from backend.apps.companies.models import Company, CustomUser, UserRole
from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import CustomerFinancialProfile, CustomerLicenseProfile
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def company() -> Company:
    return Company.objects.create(name="onboarding-tenant", tax_number="6660001111")


@pytest.fixture
def manager(company: Company) -> CustomUser:
    return CustomUser.objects.create_user(
        username="onboarding_mgr",
        password="test-pass-123",
        company=company,
        role=UserRole.FLEET_MANAGER,
    )


@pytest.fixture
def client(manager: CustomUser) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=manager)
    return api_client


def _driver_payload() -> dict:
    return {
        "driver": {
            "first_name": "Yeni",
            "last_name": "Surucu",
            "national_id": "11111111110",
            "birth_date": date.today() - timedelta(days=365 * 30),
            "phone": "5550001122",
            "license_number": "A123456",
            "city": "Ankara",
        },
        "license": {
            "license_issue_date": (date.today() - timedelta(days=365 * 5)).isoformat(),
        },
        "financial": {
            "findeks_score": 750,
        },
    }


def test_driver_create_via_api_gets_immediate_risk_score(client):
    response = client.post("/api/drivers/create/", _driver_payload(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["risk"]["skor"] is not None
    assert response.data["risk"]["seviye"]

    driver = Driver.objects.get(pk=response.data["id"])
    assert driver.current_risk_score is not None
    assert driver.risk_level
    assert driver.risk_note is not None


def test_driver_post_save_signal_evaluates_on_commit(company, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        Driver.objects.create(
            company=company,
            first_name="Signal",
            last_name="Test",
            national_id="44444444440",
            birth_date=date.today() - timedelta(days=365 * 28),
            phone="5552223344",
            license_number="S123456",
            city="Ankara",
        )

    driver = Driver.objects.get(national_id="44444444440")
    assert driver.current_risk_score is not None
    assert driver.risk_level


def test_low_risk_driver_rejected_for_premium_vehicle(company):
    driver = Driver.objects.create(
        company=company,
        first_name="Riskli",
        last_name="Surucu",
        national_id="22222222220",
        birth_date=date.today() - timedelta(days=365 * 19),
        phone="5551112233",
        license_number="X123456",
        city="Ankara",
    )
    CustomerLicenseProfile.objects.create(
        driver=driver,
        license_issue_date=date.today() - timedelta(days=180),
    )
    CustomerFinancialProfile.objects.create(
        driver=driver,
        findeks_score=400,
        payment_delay_count=1,
    )
    DriverEvaluationService().evaluate(driver)

    premium = Vehicle.objects.create(
        company=company,
        plate_number="34TST001",
        brand="Mercedes",
        model="C200",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
        purchase_price=Decimal("600000"),
    )
    Vehicle.objects.create(
        company=company,
        plate_number="34TST002",
        brand="Dacia",
        model="Sandero",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
        purchase_price=Decimal("400000"),
    )

    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(days=3)

    with pytest.raises(ValidationError) as exc_info:
        enforce_risk_and_eligibility(
            company=company,
            driver=driver,
            vehicle=premium,
            created_by=None,
            requested_pickup_at=start,
            requested_return_at=end,
        )

    assert "segment" in str(exc_info.value.detail).lower()
    driver.refresh_from_db()
    assert driver.risk_level == "HIGH"


def test_driver_list_filters_by_vehicle_eligibility(client, company):
    premium = Vehicle.objects.create(
        company=company,
        plate_number="34FLT001",
        brand="Mercedes",
        model="E200",
        production_year=2023,
        current_km=3000,
        status=VehicleStatus.AVAILABLE,
        purchase_price=Decimal("900000"),
    )

    low_risk = Driver.objects.create(
        company=company,
        first_name="Uygun",
        last_name="Surucu",
        national_id="55555555550",
        birth_date=date.today() - timedelta(days=365 * 35),
        phone="5553334455",
        license_number="U123456",
        city="Ankara",
    )
    CustomerFinancialProfile.objects.create(driver=low_risk, findeks_score=800)
    DriverEvaluationService().evaluate(low_risk)

    high_risk = Driver.objects.create(
        company=company,
        first_name="Riskli",
        last_name="Surucu",
        national_id="66666666660",
        birth_date=date.today() - timedelta(days=365 * 19),
        phone="5554445566",
        license_number="R123456",
        city="Ankara",
    )
    CustomerLicenseProfile.objects.create(
        driver=high_risk,
        license_issue_date=date.today() - timedelta(days=180),
    )
    CustomerFinancialProfile.objects.create(
        driver=high_risk,
        findeks_score=400,
        payment_delay_count=1,
    )
    DriverEvaluationService().evaluate(high_risk)

    response = client.get(f"/api/drivers/?vehicle_id={premium.pk}")
    assert response.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in response.data["surucular"]}
    assert high_risk.pk not in ids
    if low_risk.risk_level in {"VERY_LOW", "LOW"}:
        assert low_risk.pk in ids
