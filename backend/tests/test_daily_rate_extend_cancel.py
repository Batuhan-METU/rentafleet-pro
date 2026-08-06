"""Günlük fiyat, kiralama uzatma ve iptal/erken-teslim ayrımı testleri."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError

from backend.application.rental.return_processing import (
    extend_active_rental,
    process_vehicle_return,
)
from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import Rental, RentalStatus, ReturnStatus
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def driver(company: Company) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Dre",
        last_name="Sürücü",
        national_id="66666666660",
        birth_date=date.today() - timedelta(days=365 * 35),
        phone="5551112233",
        license_number="D111222",
        city="Ankara",
    )


@pytest.fixture
def vehicle(company: Company) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number="34DRE001",
        brand="Fiat",
        model="Egea",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.RENTED,
    )


def _rental(
    driver: Driver,
    vehicle: Vehicle,
    *,
    days: int = 5,
    daily_rate=Decimal("4000"),
    status_=RentalStatus.ACTIVE,
    started_offset_days: int = 2,
) -> Rental:
    started_at = timezone.now() - timedelta(days=started_offset_days)
    ended_at = started_at + timedelta(days=days)
    return Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=status_,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=daily_rate,
    )


def test_daily_rate_used_directly_no_division(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("4000"))
    actual_return_at = rental.ended_at - timedelta(days=2)

    settlement = process_vehicle_return(rental, actual_return_at, "günlük fiyat testi")

    assert settlement.return_status == ReturnStatus.EARLY
    assert settlement.unused_days == 2
    assert settlement.price_difference == Decimal("-8000.00")


def test_extension_full_use_no_penalty(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("1000"))
    new_ended_at = rental.ended_at + timedelta(days=3)

    extend_active_rental(rental, new_ended_at)
    rental.refresh_from_db()
    assert rental.ended_at == new_ended_at
    assert rental.original_ended_at != new_ended_at

    settlement = process_vehicle_return(rental, new_ended_at)

    assert settlement.return_status == ReturnStatus.LATE
    assert settlement.price_difference == Decimal("3000.00")  # 3 gün × 1000, cezasız


def test_extension_plus_unplanned_overage_combines_charges(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("1000"))
    new_ended_at = rental.ended_at + timedelta(days=3)
    extend_active_rental(rental, new_ended_at)
    rental.refresh_from_db()

    actual_return_at = new_ended_at + timedelta(days=1)
    settlement = process_vehicle_return(rental, actual_return_at)

    assert settlement.return_status == ReturnStatus.LATE
    # Planlı: 3 gün × 1000 = 3000 (cezasız). Plansız aşım: 1 gün × 1000 × 1.25 = 1250.
    assert settlement.price_difference == Decimal("4250.00")


def test_extension_rejected_on_vehicle_conflict(driver, vehicle):
    rental = _rental(driver, vehicle, days=5, daily_rate=Decimal("1000"))
    original_ended_at = rental.ended_at

    other_driver = Driver.objects.create(
        company=vehicle.company,
        first_name="Diger",
        last_name="Surucu",
        national_id="77777777770",
        birth_date=date.today() - timedelta(days=365 * 30),
        phone="5553334455",
        license_number="D333444",
        city="Ankara",
    )
    Rental.objects.create(
        driver=other_driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=original_ended_at + timedelta(days=1),
        ended_at=original_ended_at + timedelta(days=6),
        original_ended_at=original_ended_at + timedelta(days=6),
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    with pytest.raises(ValidationError):
        extend_active_rental(rental, original_ended_at + timedelta(days=3))

    rental.refresh_from_db()
    assert rental.ended_at == original_ended_at


def test_future_reservation_cancel_has_no_price_difference(client, driver, vehicle):
    started_at = timezone.now() + timedelta(days=3)
    ended_at = started_at + timedelta(days=5)
    rental = Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )
    vehicle.status = VehicleStatus.AVAILABLE
    vehicle.save(update_fields=["status"])

    resp = client.post(f"/api/rentals/{rental.pk}/cancel/", format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["status"] == RentalStatus.CANCELLED
    assert resp.data.get("price_difference") in (None, "0.00")


def test_active_reservation_cancel_is_treated_as_early_return(client, driver, vehicle):
    started_at = timezone.now() - timedelta(days=2)
    ended_at = started_at + timedelta(days=10)
    rental = Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    resp = client.post(f"/api/rentals/{rental.pk}/cancel/", format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["status"] == ReturnStatus.EARLY
    assert Decimal(resp.data["price_difference"]) < 0

    rental.refresh_from_db()
    assert rental.status == RentalStatus.COMPLETED
    assert rental.return_status == ReturnStatus.EARLY


def test_overdue_active_rental_stays_active_but_is_flagged(client, driver, vehicle):
    # Sözleşme bitiş tarihi geçmiş ama araç henüz "Teslim Al" ile
    # kapatılmadığı için status hâlâ ACTIVE — ayrı bir "Gecikmiş" kategorisi
    # yok, kiralama Aktif kalır ama `is_overdue=True` ile bayraklanır ve
    # sekme özetindeki `active_overdue` sayacına dahil olur.
    started_at = timezone.now() - timedelta(days=10)
    ended_at = timezone.now() - timedelta(days=1)
    Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=ended_at,
        original_ended_at=ended_at,
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    active_resp = client.get("/api/rentals/", {"period": "ACTIVE"}, format="json")
    assert active_resp.status_code == status.HTTP_200_OK
    assert active_resp.data["total"] == 1
    assert active_resp.data["rentals"][0]["period_code"] == "ACTIVE"
    assert active_resp.data["rentals"][0]["period_label"] == "Aktif"
    assert active_resp.data["rentals"][0]["is_overdue"] is True
    assert active_resp.data["summary"]["active_overdue"] == 1

    past_resp = client.get("/api/rentals/", {"period": "PAST"}, format="json")
    assert past_resp.status_code == status.HTTP_200_OK
    assert past_resp.data.get("count", 0) == 0


def test_active_rental_not_yet_due_is_not_overdue(client, driver, vehicle):
    rental = _rental(driver, vehicle, days=5, started_offset_days=2)

    resp = client.get("/api/rentals/", {"period": "ACTIVE"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["total"] == 1
    assert resp.data["rentals"][0]["id"] == rental.id
    assert resp.data["rentals"][0]["is_overdue"] is False
    assert resp.data["summary"]["active_overdue"] == 0


def test_rental_ordering_has_unique_tiebreaker():
    # started_at TEK BAŞINA benzersiz değildir (bkz. Rental.Meta.ordering
    # docstring'i) — bir tiebreaker olmadan sayfalanan listelerde aynı kayıt
    # iki sayfada birden çıkabilir/hiç çıkmayabilir. Bu test o regresyonun
    # sessizce geri gelmesini engeller.
    assert "id" in {f.lstrip("-") for f in Rental._meta.ordering}


def test_past_pagination_has_no_overlap_when_started_at_ties(client, driver, vehicle):
    # 25 tamamlanmış kiralama, HEPSİ BİREBİR AYNI started_at ile (gerçek
    # veride binlerce böyle eşitlik var) — tiebreaker olmadan bu, sayfa
    # sınırındaki kayıtların iki sayfada birden çıkmasına yol açabiliyordu.
    same_started_at = timezone.now() - timedelta(days=30)
    same_ended_at = same_started_at + timedelta(days=3)
    for _ in range(25):
        Rental.objects.create(
            driver=driver,
            vehicle=vehicle,
            status=RentalStatus.COMPLETED,
            started_at=same_started_at,
            ended_at=same_ended_at,
            original_ended_at=same_ended_at,
            start_km=vehicle.current_km,
            daily_rate=Decimal("1000"),
        )

    page1 = client.get("/api/rentals/", {"period": "PAST", "page": 1}, format="json")
    page2 = client.get("/api/rentals/", {"period": "PAST", "page": 2}, format="json")
    ids_page1 = [r["id"] for r in page1.data["results"]]
    ids_page2 = [r["id"] for r in page2.data["results"]]

    assert len(ids_page1) == 20
    assert len(ids_page2) == 5
    assert set(ids_page1).isdisjoint(ids_page2)
    assert len(set(ids_page1 + ids_page2)) == 25


def test_create_rental_uses_agreed_pickup_and_dropoff_time(client, driver, vehicle):
    vehicle.status = "AVAILABLE"
    vehicle.save(update_fields=["status"])
    pickup = (timezone.now() + timedelta(days=1)).date()
    dropoff = pickup + timedelta(days=3)

    resp = client.post(
        "/api/rentals/",
        {
            "driver_id": driver.id,
            "vehicle_id": vehicle.id,
            "pickup_date": pickup.isoformat(),
            "dropoff_date": dropoff.isoformat(),
            "pickup_time": "14:30",
            "dropoff_time": "09:15",
            "daily_rate": "1000",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    rental = Rental.objects.get(pk=resp.data["id"])
    started_local = timezone.localtime(rental.started_at)
    ended_local = timezone.localtime(rental.ended_at)
    assert (started_local.hour, started_local.minute) == (14, 30)
    assert (ended_local.hour, ended_local.minute) == (9, 15)


def test_create_rental_defaults_to_ten_am_without_explicit_time(client, driver, vehicle):
    vehicle.status = "AVAILABLE"
    vehicle.save(update_fields=["status"])
    pickup = (timezone.now() + timedelta(days=1)).date()
    dropoff = pickup + timedelta(days=3)

    resp = client.post(
        "/api/rentals/",
        {
            "driver_id": driver.id,
            "vehicle_id": vehicle.id,
            "pickup_date": pickup.isoformat(),
            "dropoff_date": dropoff.isoformat(),
            "daily_rate": "1000",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    rental = Rental.objects.get(pk=resp.data["id"])
    started_local = timezone.localtime(rental.started_at)
    ended_local = timezone.localtime(rental.ended_at)
    assert (started_local.hour, started_local.minute) == (10, 0)
    assert (ended_local.hour, ended_local.minute) == (10, 0)


def test_past_period_is_paginated_20_per_page_newest_first(client, driver, vehicle):
    # 25 tamamlanmış kiralama — hepsi tek seferde değil, 20'şer sayfa
    # halinde, en yeni başlangıçtan en eskiye doğru gelmeli.
    for i in range(25):
        _rental(
            driver,
            vehicle,
            days=3,
            status_=RentalStatus.COMPLETED,
            started_offset_days=30 + i,  # her biri farklı (ve giderek eski) bir tarihte başladı
        )

    page1 = client.get("/api/rentals/", {"period": "PAST"}, format="json")
    assert page1.status_code == status.HTTP_200_OK
    assert page1.data["count"] == 25
    assert len(page1.data["results"]) == 20
    assert page1.data["next"] is not None
    assert page1.data["summary"]["past"] == 25
    # En yeni (en küçük started_offset_days) önce gelmeli.
    first_started = page1.data["results"][0]["started_at"]
    last_started_on_page1 = page1.data["results"][-1]["started_at"]
    assert first_started > last_started_on_page1

    page2 = client.get("/api/rentals/", {"period": "PAST", "page": 2}, format="json")
    assert page2.status_code == status.HTTP_200_OK
    assert len(page2.data["results"]) == 5
    assert page2.data["previous"] is not None
    assert page2.data["next"] is None
