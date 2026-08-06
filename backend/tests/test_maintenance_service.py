"""maintenance_service.py — çift boyutlu (km + tarih) bakım durumu hesabı.

Gerçek kural: son bakımdan itibaren 10.000-15.000 km ARASI veya en geç 12
ay geçince bakım şart, hangisi önce dolarsa. "Son bakım", VEHICLE_
MAINTENANCE kategorili en son VehicleExpense kaydından türetilir; yoksa
filoya giriş tarihi + satın alma km'sine düşülür (§1.5 "Bilinmiyor ≠ Sıfır"
prensibiyle: km bilinmiyorsa km boyutu None, asla sahte 0/sağlıklı değil).
"""

from __future__ import annotations

from datetime import date

import pytest

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.choices import ExpenseCategory
from backend.apps.vehicle_finance.models import VehicleExpense, VehicleFinancialProfile
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.analytics.maintenance_service import (
    STATUS_CRITICAL,
    STATUS_HEALTHY,
    STATUS_WARNING,
    get_maintenance_statuses,
)
from backend.infrastructure.services.cost_calculation.day_math import add_months

pytestmark = pytest.mark.django_db

TODAY = date(2026, 6, 15)


def _vehicle(company: Company, plate: str, current_km: int, **kwargs) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=plate,
        brand="Renault",
        model="Clio",
        production_year=2023,
        current_km=current_km,
        **kwargs,
    )


def _maintenance(vehicle: Vehicle, *, expense_date: date, odometer_km: int | None) -> VehicleExpense:
    return VehicleExpense.objects.create(
        vehicle=vehicle,
        category=ExpenseCategory.VEHICLE_MAINTENANCE,
        amount="750.00",
        expense_date=expense_date,
        odometer_km=odometer_km,
    )


def _status_for(company: Company, plate: str):
    return next(s for s in get_maintenance_statuses(company.pk, as_of=TODAY) if s.plate == plate)


def test_healthy_recent_maintenance_low_km(company: Company) -> None:
    vehicle = _vehicle(company, "34BKM001", current_km=2_000)
    _maintenance(vehicle, expense_date=add_months(TODAY, -2), odometer_km=0)

    s = _status_for(company, "34BKM001")
    assert s.km_status == STATUS_HEALTHY
    assert s.date_status == STATUS_HEALTHY
    assert s.status == STATUS_HEALTHY


def test_approaching_km_window(company: Company) -> None:
    # Hedef 15.000 km; kalan 1.500 km <= 2.000 km tampon penceresi → WARNING.
    vehicle = _vehicle(company, "34BKM002", current_km=13_500)
    _maintenance(vehicle, expense_date=add_months(TODAY, -1), odometer_km=0)

    s = _status_for(company, "34BKM002")
    assert s.km_status == STATUS_WARNING
    assert s.date_status == STATUS_HEALTHY
    assert s.status == STATUS_WARNING


def test_overdue_by_date_only(company: Company) -> None:
    vehicle = _vehicle(company, "34BKM003", current_km=500)
    _maintenance(vehicle, expense_date=add_months(TODAY, -13), odometer_km=0)

    s = _status_for(company, "34BKM003")
    assert s.km_status == STATUS_HEALTHY
    assert s.date_status == STATUS_CRITICAL
    assert s.status == STATUS_CRITICAL


def test_overdue_by_km_only(company: Company) -> None:
    vehicle = _vehicle(company, "34BKM004", current_km=16_000)
    _maintenance(vehicle, expense_date=add_months(TODAY, -0), odometer_km=0)

    s = _status_for(company, "34BKM004")
    assert s.km_status == STATUS_CRITICAL
    assert s.date_status == STATUS_HEALTHY
    assert s.status == STATUS_CRITICAL


def test_no_maintenance_history_falls_back_to_fleet_entry(company: Company) -> None:
    vehicle = _vehicle(
        company, "34BKM005", current_km=13_500, fleet_entry_date=add_months(TODAY, -1)
    )
    assert vehicle.fleet_entry_date is not None
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle, purchase_date=vehicle.fleet_entry_date, purchase_price="500000", purchase_km=0
    )

    s = _status_for(company, "34BKM005")
    assert s.last_maintenance_date == vehicle.fleet_entry_date
    assert s.last_maintenance_km == 0
    assert s.km_status == STATUS_WARNING  # kalan 1.500 km <= 2.000 km tampon penceresi
    assert s.date_status == STATUS_HEALTHY


def test_no_maintenance_history_and_no_financial_profile_km_unknown(company: Company) -> None:
    _vehicle(company, "34BKM006", current_km=20_000, fleet_entry_date=add_months(TODAY, -14))
    # Kasıtlı olarak VehicleFinancialProfile OLUŞTURULMUYOR.

    s = _status_for(company, "34BKM006")
    assert s.last_maintenance_km is None
    assert s.km_status is None
    assert s.target_km is None
    assert s.remaining_km is None
    assert s.progress_pct is None
    assert s.date_status == STATUS_CRITICAL  # 14 ay geçmiş
    assert s.status == STATUS_CRITICAL  # sadece tarihten geliyor


def test_maintenance_record_missing_odometer_km(company: Company) -> None:
    vehicle = _vehicle(company, "34BKM007", current_km=50_000)
    _maintenance(vehicle, expense_date=add_months(TODAY, -1), odometer_km=None)

    s = _status_for(company, "34BKM007")
    assert s.last_maintenance_km is None
    assert s.km_status is None
    assert s.target_km is None
    assert s.remaining_km is None
    assert s.progress_pct is None
    assert s.date_status == STATUS_HEALTHY
    assert s.status == STATUS_HEALTHY  # bilinmeyen km boyutu alarme yol açmaz


def test_uses_most_recent_maintenance_record(company: Company) -> None:
    vehicle = _vehicle(company, "34BKM008", current_km=10_500)
    _maintenance(vehicle, expense_date=add_months(TODAY, -20), odometer_km=0)  # eski
    _maintenance(vehicle, expense_date=add_months(TODAY, -1), odometer_km=10_000)  # yeni

    s = _status_for(company, "34BKM008")
    assert s.last_maintenance_km == 10_000
    assert s.km_status == STATUS_HEALTHY  # 500 km since last (yeni kayda göre), eskiye göre değil


def test_vehicle_mechanical_category_not_counted_as_maintenance(company: Company) -> None:
    vehicle = _vehicle(
        company, "34BKM009", current_km=12_000, fleet_entry_date=add_months(TODAY, -1)
    )
    assert vehicle.fleet_entry_date is not None
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle, purchase_date=vehicle.fleet_entry_date, purchase_price="500000", purchase_km=0
    )
    # Çok yakın tarihli bir ARIZA (mekanik) kaydı — bakım sayılmamalı.
    VehicleExpense.objects.create(
        vehicle=vehicle,
        category=ExpenseCategory.VEHICLE_MECHANICAL,
        amount="300.00",
        expense_date=TODAY,
        odometer_km=11_999,
    )

    s = _status_for(company, "34BKM009")
    # Referans hâlâ filoya giriş noktası olmalı (mekanik kayda göre DEĞİL).
    assert s.last_maintenance_date == vehicle.fleet_entry_date
    assert s.last_maintenance_km == 0


def test_sort_order_critical_then_warning_then_healthy(company: Company) -> None:
    healthy = _vehicle(company, "34BKM010", current_km=1_000)
    _maintenance(healthy, expense_date=add_months(TODAY, -1), odometer_km=0)

    warning = _vehicle(company, "34BKM011", current_km=11_000)
    _maintenance(warning, expense_date=add_months(TODAY, -1), odometer_km=0)

    critical = _vehicle(company, "34BKM012", current_km=16_000)
    _maintenance(critical, expense_date=add_months(TODAY, -1), odometer_km=0)

    statuses = get_maintenance_statuses(company.pk, as_of=TODAY)
    plates = [s.plate for s in statuses]
    assert plates.index("34BKM012") < plates.index("34BKM011") < plates.index("34BKM010")


def test_multi_tenant_isolation(company: Company) -> None:
    _vehicle(company, "34BKM013", current_km=1_000)
    rival = Company.objects.create(name="bakim-rival", tax_number="9990002222")
    _vehicle(rival, "06RKP001", current_km=1_000)

    statuses = get_maintenance_statuses(company.pk, as_of=TODAY)
    assert [s.plate for s in statuses] == ["34BKM013"]
