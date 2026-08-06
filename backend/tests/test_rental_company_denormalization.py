"""`Rental.company` denormalizasyonu — save() otomatik doldurma + kiracı
izolasyonunun artık driver JOIN'i olmadan da doğru çalıştığını doğrular."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import Rental, RentalStatus
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


def _driver(company: Company, suffix: str) -> Driver:
    return Driver.objects.create(
        company=company,
        first_name="Test",
        last_name=suffix,
        national_id=f"333333{suffix}0",
        birth_date=timezone.now().date() - timedelta(days=365 * 30),
        phone=f"5550001{suffix}",
        license_number=f"L{suffix}",
        city="Ankara",
    )


def _vehicle(company: Company, suffix: str) -> Vehicle:
    return Vehicle.objects.create(
        company=company,
        plate_number=f"06CO{suffix}",
        brand="Renault",
        model="Clio",
        production_year=2023,
        current_km=1000,
        status=VehicleStatus.AVAILABLE,
        purchase_price=Decimal("700000"),
    )


def test_rental_save_auto_populates_company_from_driver(company: Company) -> None:
    driver = _driver(company, "A")
    vehicle = _vehicle(company, "A")
    started_at = timezone.now()

    rental = Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=started_at + timedelta(days=3),
        original_ended_at=started_at + timedelta(days=3),
        start_km=vehicle.current_km,
        daily_rate=Decimal("1000"),
    )

    assert rental.company_id == company.pk


def test_rental_company_filter_matches_driver_company_filter(company: Company) -> None:
    other_company = Company.objects.create(name="other-rental-co", tax_number="8880008888")
    driver_a = _driver(company, "B")
    vehicle_a = _vehicle(company, "B")
    driver_b = _driver(other_company, "C")
    vehicle_b = _vehicle(other_company, "C")
    started_at = timezone.now()

    rental_a = Rental.objects.create(
        driver=driver_a,
        vehicle=vehicle_a,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=started_at + timedelta(days=2),
        original_ended_at=started_at + timedelta(days=2),
        start_km=vehicle_a.current_km,
        daily_rate=Decimal("900"),
    )
    Rental.objects.create(
        driver=driver_b,
        vehicle=vehicle_b,
        status=RentalStatus.ACTIVE,
        started_at=started_at,
        ended_at=started_at + timedelta(days=2),
        original_ended_at=started_at + timedelta(days=2),
        start_km=vehicle_b.current_km,
        daily_rate=Decimal("900"),
    )

    # Yeni doğrudan `company` alanı, eski `driver__company` JOIN'iyle
    # BİREBİR aynı sonucu vermeli — sadece JOIN'siz.
    scoped = Rental.objects.filter(company=company)
    assert list(scoped) == [rental_a]
    assert scoped.count() == Rental.objects.filter(driver__company=company).count()
