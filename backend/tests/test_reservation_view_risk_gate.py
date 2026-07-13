"""POST /api/rentals/ — risk kapısının view seviyesinde uçtan uca doğrulaması.

En kritik regresyon: ``enforce_risk_and_eligibility`` ValidationError
fırlattığında, view'ın DIŞ transaction'ı (varsa) o ana kadar yazılmış olan
RentalApplication/RentalDecisionLog audit kayıtlarını da geri almamalı.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.companies.models import Company, CustomUser, UserRole
from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import (
    CustomerFinancialProfile,
    CustomerLicenseProfile,
    DecisionStep,
    RentalApplication,
    RentalDecisionLog,
)
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def company() -> Company:
    return Company.objects.create(name="test-tenant", tax_number="5559990000")


@pytest.fixture
def manager(company: Company) -> CustomUser:
    return CustomUser.objects.create_user(
        username="test_mudur",
        password="test-pass-123",
        company=company,
        role=UserRole.FLEET_MANAGER,
    )


@pytest.fixture
def client(manager: CustomUser) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=manager)
    return api_client


def _high_risk_driver(company: Company) -> Driver:
    driver = Driver.objects.create(
        company=company,
        first_name="Riskli",
        last_name="Sürücü",
        national_id="33333333330",
        birth_date=date.today() - timedelta(days=365 * 19),
        phone="5551112233",
        license_number="X999999",
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
    return driver


def _vehicle(company: Company, *, brand: str, plate: str) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=plate,
        brand=brand,
        model="Model",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
        purchase_price=Decimal("600000"),
    )


def _payload(driver: Driver, vehicle: Vehicle) -> dict:
    pickup = date.today() + timedelta(days=1)
    dropoff = pickup + timedelta(days=3)
    return {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": pickup.isoformat(),
        "dropoff_date": dropoff.isoformat(),
    }


def test_rejected_reservation_returns_400_and_persists_decision_log(client, company):
    driver = _high_risk_driver(company)
    premium = _vehicle(company, brand="Mercedes", plate="34VG001")
    _vehicle(company, brand="Dacia", plate="34VG002")  # eligible alternative

    response = client.post("/api/rentals/", _payload(driver, premium), format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "segment" in str(response.data.get("error", "")).lower()

    # Kritik regresyon kontrolü: reddedilen deneme, dış view transaction'ı
    # tarafından geri alınmamış — RentalApplication ve RISK adımı audit
    # kaydı kalıcı olarak veritabanında.
    application = RentalApplication.objects.filter(driver=driver).first()
    assert application is not None
    assert RentalDecisionLog.objects.filter(
        application=application, step=DecisionStep.RISK
    ).exists()
    assert RentalDecisionLog.objects.filter(
        application=application, step=DecisionStep.ELIGIBILITY, approved=False
    ).exists()


def test_blacklisted_driver_rejected_with_persistent_audit_log(client, company):
    """Kara liste kontrolü artık view'da erken-dönüş değil, risk kapısında.

    Böylece kara listeli sürücünün denemesi de RentalDecisionLog'a düşer
    (erken-dönüş sürümünde bu deneme hiç loglanmıyordu).
    """
    driver = _high_risk_driver(company)
    driver.is_blacklisted = True
    driver.save(update_fields=["is_blacklisted"])
    economy = _vehicle(company, brand="Dacia", plate="34VG005")

    response = client.post("/api/rentals/", _payload(driver, economy), format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "risk skoru yetersiz" in str(response.data.get("error", "")).lower()

    application = RentalApplication.objects.filter(driver=driver).first()
    assert application is not None
    risk_log = RentalDecisionLog.objects.get(application=application, step=DecisionStep.RISK)
    assert risk_log.approved is False
    assert any("kara listesinde" in b for b in risk_log.output_snapshot.get("blockers", []))


def test_approved_reservation_creates_rental_linked_to_application(client, company):
    driver = _high_risk_driver(company)
    economy = _vehicle(company, brand="Dacia", plate="34VG003")

    response = client.post("/api/rentals/", _payload(driver, economy), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    application = RentalApplication.objects.get(driver=driver)
    assert application.risk_level == "HIGH"

    rental_id = response.data["id"]
    from backend.apps.reservations.models import Rental

    rental = Rental.objects.get(pk=rental_id)
    assert rental.application_id == application.pk
