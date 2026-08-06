"""POST /api/rentals/ — `Idempotency-Key` header desteği.

Aynı anahtarla tekrarlanan bir istek (ör. ağ zaman aşımı sonrası istemci
yeniden denemesi) ikinci bir kiralama OLUŞTURMAMALI, ilk yanıtı aynen
döndürmeli. Anahtar hiç gönderilmezse davranış birebir eskisi gibi kalır.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework import status

from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver
from backend.apps.idempotency.models import IdempotencyRecord
from backend.apps.rentals.models import Rental
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


def _driver(company: Company) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Idempotent",
        last_name="Sürücü",
        national_id="66666666660",
        birth_date=date.today() - timedelta(days=365 * 30),
        phone="5556667788",
        license_number="I000111",
        city="Ankara",
    )


def _vehicle(company: Company) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number="34IDK001",
        brand="Dacia",
        model="Sandero",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
    )


def _payload(driver: Driver, vehicle: Vehicle) -> dict:
    return {
        "driver_id": driver.pk,
        "vehicle_id": vehicle.pk,
        "pickup_date": (date.today() + timedelta(days=1)).isoformat(),
        "dropoff_date": (date.today() + timedelta(days=4)).isoformat(),
    }


def test_repeated_request_with_same_idempotency_key_creates_only_one_rental(client, company):
    driver = _driver(company)
    vehicle = _vehicle(company)
    payload = _payload(driver, vehicle)
    headers = {"HTTP_IDEMPOTENCY_KEY": "test-key-abc-123"}

    first = client.post("/api/rentals/", payload, format="json", **headers)
    assert first.status_code == status.HTTP_201_CREATED
    assert Rental.objects.filter(driver=driver).count() == 1

    second = client.post("/api/rentals/", payload, format="json", **headers)
    assert second.status_code == status.HTTP_201_CREATED
    assert second.data == first.data
    # En kritik doğrulama: ikinci istek yeni bir kiralama YARATMADI.
    assert Rental.objects.filter(driver=driver).count() == 1


def test_different_idempotency_keys_create_separate_rentals(client, company):
    driver = _driver(company)
    vehicle_a = _vehicle(company)
    vehicle_b = Vehicle.objects.create(
        company=company,
        plate_number="34IDK002",
        brand="Dacia",
        model="Duster",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
    )

    client.post(
        "/api/rentals/", _payload(driver, vehicle_a), format="json", HTTP_IDEMPOTENCY_KEY="key-1"
    )
    driver.rentals.update(status="CANCELLED")  # ilkini kapat, çakışma olmasın
    client.post(
        "/api/rentals/", _payload(driver, vehicle_b), format="json", HTTP_IDEMPOTENCY_KEY="key-2"
    )

    assert Rental.objects.filter(driver=driver).count() == 2


def test_no_idempotency_key_behaves_exactly_as_before(client, company):
    driver = _driver(company)
    vehicle = _vehicle(company)
    payload = _payload(driver, vehicle)

    response = client.post("/api/rentals/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert IdempotencyRecord.objects.count() == 0


def test_a_rejected_request_does_not_permanently_poison_its_idempotency_key(client, company):
    """Regresyon: `enforce_risk_and_eligibility` reddedilince ValidationError
    FIRLATIR (Response döndürmez) — dekoratör bu durumda "beklemede" kaydı
    silmezse, aynı anahtar SONSUZA DEK 409 "işleniyor" döndürürdü; sürücü
    daha sonra düzeltilip AYNI anahtarla tekrar denense bile asla
    başaramazdı. Bu test, reddedilen bir denemeden SONRA aynı anahtarla
    yapılan yeni bir denemenin gerçekten işlenebildiğini doğrular."""
    driver = _driver(company)
    driver.is_blacklisted = True
    driver.save(update_fields=["is_blacklisted"])
    vehicle = _vehicle(company)
    payload = _payload(driver, vehicle)
    headers = {"HTTP_IDEMPOTENCY_KEY": "retry-after-rejection-key"}

    rejected = client.post("/api/rentals/", payload, format="json", **headers)
    assert rejected.status_code == status.HTTP_400_BAD_REQUEST
    # "Beklemede" kayıt kalmamalı — reddedilen deneme anahtarı kilitlememeli.
    assert not IdempotencyRecord.objects.filter(key="retry-after-rejection-key").exists()

    driver.is_blacklisted = False
    driver.save(update_fields=["is_blacklisted"])

    retried = client.post("/api/rentals/", payload, format="json", **headers)
    assert retried.status_code == status.HTTP_201_CREATED
    assert Rental.objects.filter(driver=driver).exists()
