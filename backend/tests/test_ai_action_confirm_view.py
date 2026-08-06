"""POST /api/ai/actions/<uuid>/confirm/ — AI onay kartı çalıştırma uç noktası.

En kritik doğrulamalar: şirketler-arası izolasyon, tek kullanımlık tüketim
(çift onaylama), süre dolumu. Bunlar `common/idempotency.py`'deki mutex
deseniyle aynı aile — bu yüzden aynı titizlikle test edilir.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.ai.models import AIPendingAction
from backend.apps.companies.choices import UserRole
from backend.apps.companies.models import Company, CustomUser
from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import Rental
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


def _driver(company: Company) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Onay",
        last_name="Sürücü",
        national_id="88888888880",
        birth_date=date.today() - timedelta(days=365 * 30),
        phone="5551112233",
        license_number="C000111",
        city="Ankara",
    )


def _vehicle(company: Company) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number="34ONY001",
        brand="Dacia",
        model="Sandero",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
    )


def _create_rental_pending(company: Company, manager: CustomUser, driver: Driver, vehicle: Vehicle, **overrides) -> AIPendingAction:
    defaults = dict(
        company=company,
        requested_by=manager,
        tool_name="create_rental",
        arguments={
            "driver_id": driver.pk,
            "vehicle_id": vehicle.pk,
            "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
            "dropoff_date": (date.today() + timedelta(days=4)).isoformat(),
        },
        summary="Test kiralaması onayı.",
    )
    defaults.update(overrides)
    return AIPendingAction.objects.create(**defaults)


def _confirm_url(pending: AIPendingAction) -> str:
    return f"/api/ai/actions/{pending.id}/confirm/"


def test_confirming_a_valid_pending_action_creates_the_rental(client, company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    pending = _create_rental_pending(company, manager, driver, vehicle)

    response = client.post(_confirm_url(pending))

    assert response.status_code == status.HTTP_200_OK
    assert Rental.objects.filter(driver=driver, vehicle=vehicle).exists()
    pending.refresh_from_db()
    assert pending.consumed_at is not None


def test_confirming_the_same_action_twice_fails_the_second_time(client, company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    pending = _create_rental_pending(company, manager, driver, vehicle)

    first = client.post(_confirm_url(pending))
    assert first.status_code == status.HTTP_200_OK

    second = client.post(_confirm_url(pending))
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    # İkinci onay YENİ bir kiralama YARATMADI.
    assert Rental.objects.filter(driver=driver, vehicle=vehicle).count() == 1


def test_confirming_an_expired_action_fails_and_does_not_execute(client, company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    pending = _create_rental_pending(
        company, manager, driver, vehicle, expires_at=timezone.now() - timedelta(minutes=1)
    )

    response = client.post(_confirm_url(pending))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Rental.objects.filter(driver=driver, vehicle=vehicle).exists()


def test_a_different_companys_user_cannot_confirm_someone_elses_pending_action(company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    pending = _create_rental_pending(company, manager, driver, vehicle)

    other_company = Company.objects.create(name="other-tenant-2", tax_number="0000000003")
    other_user = CustomUser.objects.create_user(
        username="other_manager_2",
        password="test-pass-123",
        company=other_company,
        role=UserRole.FLEET_MANAGER,
    )
    other_client = APIClient()
    other_client.force_authenticate(user=other_user)

    response = other_client.post(_confirm_url(pending))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not Rental.objects.filter(driver=driver, vehicle=vehicle).exists()
    pending.refresh_from_db()
    assert pending.consumed_at is None


def test_confirming_a_nonexistent_action_returns_404(client):
    response = client.post("/api/ai/actions/00000000-0000-0000-0000-000000000000/confirm/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_failed_execution_does_not_consume_the_action_and_can_be_retried(client, company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    # Aracı meşgul yaparak `create_rental`'ın başarısız olmasını sağla.
    vehicle.status = VehicleStatus.MAINTENANCE
    vehicle.save(update_fields=["status"])
    pending = _create_rental_pending(company, manager, driver, vehicle)

    failed = client.post(_confirm_url(pending))
    assert failed.status_code == status.HTTP_400_BAD_REQUEST
    pending.refresh_from_db()
    assert pending.consumed_at is None

    # Araç tekrar müsait hale gelince AYNI action_id ile tekrar denenebilir.
    vehicle.status = VehicleStatus.AVAILABLE
    vehicle.save(update_fields=["status"])
    retried = client.post(_confirm_url(pending))
    assert retried.status_code == status.HTTP_200_OK
    assert Rental.objects.filter(driver=driver, vehicle=vehicle).exists()
