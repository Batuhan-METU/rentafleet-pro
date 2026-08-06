"""Sürücü listesi — N+1 regresyon koruması.

DriverListView eskiden her sürücü için ayrı ayrı:
  * `total_rentals` alanı için bir COUNT sorgusu (DriverSerializer),
  * risk denetimi (`driver_risk_cleared`/`driver_has_risk_approval`) için
    `risk_snapshots` üzerinde 2-3 ayrı sorgu (prefetch_related önbelleğini
    atlayan `.order_by()/.exists()` zincirlemesi yüzünden)
çalıştırıyordu — sürücü sayısı arttıkça sorgu sayısı da DOĞRUSAL artıyordu.
Bu testler, sorgu sayısının sürücü sayısından BAĞIMSIZ (sabit) kaldığını
doğrular; regresyon durumunda ikinci assert (15 sürücü) ilkinden (3 sürücü)
daha fazla sorgu gösterip testi kırar.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import Rental, RentalStatus
from backend.apps.risk_checks.models import CustomerRiskSnapshot
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


def _driver(company, idx: int) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name=f"Test{idx}",
        last_name=f"Surucu{idx}",
        national_id=f"1111111{idx:04d}",
        birth_date=date.today() - timedelta(days=365 * 30),
        phone=f"555000{idx:04d}",
        license_number=f"T{idx:06d}",
        city="Ankara",
        current_risk_score=20,
        risk_level="LOW",
    )


def _vehicle(company, idx: int) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=f"06PERF{idx:03d}",
        brand="Toyota",
        model="Corolla",
        production_year=2023,
        current_km=10_000,
        status=VehicleStatus.AVAILABLE,
        purchase_price=Decimal("900000"),
    )


def _seed_drivers_with_history(company, count: int, *, start_at_index: int = 0) -> None:
    for i in range(start_at_index, start_at_index + count):
        driver = _driver(company, i)
        vehicle = _vehicle(company, i)
        started_at = timezone_now() - timedelta(days=10)
        Rental.objects.create(
            driver=driver,
            vehicle=vehicle,
            status=RentalStatus.CANCELLED,
            started_at=started_at,
            ended_at=started_at + timedelta(days=3),
            original_ended_at=started_at + timedelta(days=3),
            start_km=vehicle.current_km,
            daily_rate=Decimal("1000"),
        )
        CustomerRiskSnapshot.objects.create(
            driver=driver,
            risk_score=20,
            risk_level="LOW",
            factor_breakdown={"audit": {"blockers": [], "eligible_vehicles": [vehicle.pk]}},
        )


def timezone_now():
    from django.utils import timezone

    return timezone.now()


def _query_count_for_driver_list(client) -> int:
    with CaptureQueriesContext(connection) as ctx:
        response = client.get("/api/drivers/")
    assert response.status_code == 200
    return len(ctx.captured_queries)


def test_driver_list_query_count_is_constant_regardless_of_driver_count(client, company):
    _seed_drivers_with_history(company, 3, start_at_index=0)
    small_count = _query_count_for_driver_list(client)

    _seed_drivers_with_history(company, 15, start_at_index=100)
    large_count = _query_count_for_driver_list(client)

    assert large_count == small_count, (
        f"Sürücü listesi sorgu sayısı sürücü sayısına göre BÜYÜDÜ "
        f"({small_count} -> {large_count}) — N+1 regresyonu."
    )


def test_driver_list_total_rentals_matches_non_cancelled_count(client, company):
    driver = _driver(company, 99)
    vehicle = _vehicle(company, 99)
    started_at = timezone_now() - timedelta(days=10)
    Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.CANCELLED,
        started_at=started_at,
        ended_at=started_at + timedelta(days=1),
        original_ended_at=started_at + timedelta(days=1),
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )
    Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.COMPLETED,
        started_at=started_at,
        ended_at=started_at + timedelta(days=2),
        original_ended_at=started_at + timedelta(days=2),
        actual_return_at=started_at + timedelta(days=2),
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    response = client.get("/api/drivers/")
    assert response.status_code == 200
    item = next(d for d in response.data["drivers"] if d["id"] == driver.pk)
    # 1 CANCELLED (hariç tutulur) + 1 COMPLETED (sayılır) = 1
    assert item["total_rentals"] == 1


def test_driver_list_is_unpaginated_by_default_for_backward_compatibility(client, company):
    _seed_drivers_with_history(company, 12)
    response = client.get("/api/drivers/")
    assert response.status_code == 200
    assert response.data["driver_count"] == 12
    assert len(response.data["drivers"]) == 12


def test_driver_list_supports_opt_in_pagination(client, company):
    _seed_drivers_with_history(company, 12)
    response = client.get("/api/drivers/?page=2&page_size=5")
    assert response.status_code == 200
    # driver_count TOPLAM eşleşen sürücü sayısıdır, sayfadaki değil.
    assert response.data["driver_count"] == 12
    assert len(response.data["drivers"]) == 5
