"""AI mutasyon tool handler'ları — doğrudan (HTTP'siz) çağrıldığında ilgili
view ile AYNI iş mantığını uyguladığını doğrular.

Handler'lar ``(request, args)`` alır; burada gerçek bir DRF ``Request``
(``APIRequestFactory`` ile) + ``user`` ataması kullanılır — tıpkı
``AIActionConfirmView``'ın gerçek çalışma zamanında yaptığı gibi.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from backend.apps.companies.models import Company, CustomUser
from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import Rental, RentalStatus
from backend.apps.vehicle_finance.models import VehicleExpense
from backend.apps.vehicles.models import Vehicle, VehicleStatus
from backend.infrastructure.services.ai.tools import read_tools, write_tools  # noqa: F401
from backend.infrastructure.services.ai.tools.registry import TOOLS

pytestmark = pytest.mark.django_db


def _request(user: CustomUser) -> Request:
    # DRF'nin `Request.user` özelliği, authenticator listesi boşsa
    # `django_request.user`'ı OKUMAZ (varsayılan olarak AnonymousUser'a
    # düşer) — bu yüzden `_user` doğrudan atanır (gerçek HTTP akışında bunu
    # TokenAuthentication yapar).
    django_request = APIRequestFactory().post("/api/ai/consult/")
    request = Request(django_request)
    request._user = user  # type: ignore[attr-defined]
    return request


def _driver(company: Company, national_id: str = "99999999990") -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Tool",
        last_name="Sürücü",
        national_id=national_id,
        birth_date=date.today() - timedelta(days=365 * 30),
        phone="5559998877",
        license_number="T000111",
        city="İzmir",
    )


def _vehicle(company: Company, plate: str = "34TOL001") -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=plate,
        brand="Renault",
        model="Clio",
        production_year=2023,
        current_km=1000,
        status=VehicleStatus.AVAILABLE,
    )


def test_create_rental_handler_creates_a_real_rental(company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    args = {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=3)).isoformat(),
    }

    result = TOOLS["create_rental"].handler(_request(manager), args)

    assert result["driver_id"] == driver.pk
    assert Rental.objects.filter(driver=driver, vehicle=vehicle, status=RentalStatus.ACTIVE).exists()


def test_create_rental_handler_rejects_conflicting_dates(company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    args = {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=3)).isoformat(),
    }
    TOOLS["create_rental"].handler(_request(manager), args)

    with pytest.raises(ValidationError):
        TOOLS["create_rental"].handler(_request(manager), args)


def test_cancel_rental_handler_cancels_a_future_rental(company, manager):
    driver = _driver(company)
    vehicle = _vehicle(company)
    rental = TOOLS["create_rental"].handler(
        _request(manager),
        {
            "driver_id": driver.pk,
            "vehicle_id": vehicle.pk,
            "pickup_date": (date.today() + timedelta(days=5)).isoformat(),
            "dropoff_date": (date.today() + timedelta(days=8)).isoformat(),
        },
    )

    result = TOOLS["cancel_rental"].handler(_request(manager), {"rental_id": rental["id"]})

    assert result["early_return"] is False
    assert Rental.objects.get(pk=rental["id"]).status == RentalStatus.CANCELLED


def test_create_vehicle_expense_generic_tool_creates_a_real_expense(company, manager):
    vehicle = _vehicle(company, plate="34TOL002")
    args = {
        "vehicle_id": vehicle.pk,
        "category": "VEHICLE_MAINTENANCE",
        "amount": "1500.00",
        "expense_date": date.today().isoformat(),
    }

    result = TOOLS["create_vehicle_expense"].handler(_request(manager), args)

    assert result["amount"] == "1500.00"
    assert VehicleExpense.objects.filter(vehicle=vehicle, amount="1500.00").exists()


def test_mutation_tool_summaries_describe_the_proposed_action(company, manager):
    driver = _driver(company, national_id="99999999991")
    vehicle = _vehicle(company, plate="34TOL003")
    args = {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=3)).isoformat(),
    }

    summary = TOOLS["create_rental"].summary(_request(manager), args)

    assert driver.full_name in summary
    assert vehicle.plate_number in summary


def test_read_tool_get_vehicle_detail_finds_vehicle_by_plate(company, manager):
    _vehicle(company, plate="34TOL004")

    result = TOOLS["get_vehicle_detail"].handler(_request(manager), {"plate_number": "34tol004"})

    assert result["plate_number"] == "34TOL004"


def test_read_tool_list_drivers_matches_multi_word_full_name(company, manager):
    driver = _driver(company, national_id="99999999992")

    result = TOOLS["list_drivers"].handler(_request(manager), {"query": f"{driver.first_name} {driver.last_name}"})

    assert result["count"] == 1
    assert result["drivers"][0]["id"] == driver.pk
