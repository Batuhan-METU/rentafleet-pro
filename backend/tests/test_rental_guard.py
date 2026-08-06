"""Kiralama risk + araç uygunluk kapısı testleri (enforce_risk_and_eligibility).

Kapsam: yüksek riskli bir sürücüye premium segment araç atanmaya
çalışıldığında sistemin reddettiğini, aynı sürücüye uygun (ekonomi) segment
bir araç önerildiğinde ise kiralamanın onaylandığını doğrular.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from backend.application.rental.rental_guard import enforce_risk_and_eligibility
from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import (
    CustomerFinancialProfile,
    CustomerLicenseProfile,
    RentalApplicationStatus,
)
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


def _high_risk_driver(company: Company) -> Driver:
    """Blok kuralı tetiklemeden HIGH risk bandına düşen bir sürücü (skor ~61-80).

    YOUNG_DRIVER_MODERATE(+15, 19<=yaş<21) + NEW_LICENSE_MODERATE(+15, 0.5-2 yıl)
    + LOW_FINDEX(+22) + PAYMENT_DELAYS(+12) + FIRST_RENTAL(+5, ilk kiralama
    olduğu için otomatik) = 69 -> HIGH. Yaş/ehliyet süresi kasıtlı olarak
    "severe" kademesine (yaş<19 / ehliyet<6 ay) düşmeyecek şekilde seçildi —
    aksi halde skor VERY_HIGH bandına taşıp bu testin senaryosunu bozar.
    Hiçbir BLOCK kuralı (kara liste, banka kara listesi, dolandırıcılık, icra)
    tetiklenmez, yani risk onayı geçer ama segment ECONOMY ile sınırlı kalır.
    """
    driver = Driver.objects.create(
        company=company,
        first_name="Riskli",
        last_name="Sürücü",
        national_id="22222222220",
        birth_date=date.today() - timedelta(days=365 * 20 + 100),
        phone="5551112233",
        license_number="X123456",
        city="Ankara",
    )
    CustomerLicenseProfile.objects.create(
        driver=driver,
        license_issue_date=date.today() - timedelta(days=400),
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


def _reservation_window() -> tuple:
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(days=3)
    return start, end


def test_high_risk_driver_blocked_from_premium_vehicle(company):
    driver = _high_risk_driver(company)
    _vehicle(company, brand="Dacia", plate="34RSK001")  # uygun (economy) alternatif
    premium = _vehicle(company, brand="Mercedes", plate="34RSK002")
    start, end = _reservation_window()

    with pytest.raises(ValidationError) as exc_info:
        enforce_risk_and_eligibility(
            company=company,
            driver=driver,
            vehicle=premium,
            created_by=None,
            requested_pickup_at=start,
            requested_return_at=end,
        )

    detail = str(exc_info.value.detail)
    assert "segment" in detail.lower()


def test_high_risk_driver_allowed_matching_economy_vehicle(company):
    driver = _high_risk_driver(company)
    economy = _vehicle(company, brand="Dacia", plate="34RSK003")
    start, end = _reservation_window()

    application = enforce_risk_and_eligibility(
        company=company,
        driver=driver,
        vehicle=economy,
        created_by=None,
        requested_pickup_at=start,
        requested_return_at=end,
    )

    assert application.status == RentalApplicationStatus.EVALUATED
    assert application.risk_level == "HIGH"


def test_blacklisted_driver_blocked_regardless_of_vehicle(company):
    driver = _high_risk_driver(company)
    driver.is_blacklisted = True
    driver.save(update_fields=["is_blacklisted"])
    economy = _vehicle(company, brand="Dacia", plate="34RSK004")
    start, end = _reservation_window()

    with pytest.raises(ValidationError) as exc_info:
        enforce_risk_and_eligibility(
            company=company,
            driver=driver,
            vehicle=economy,
            created_by=None,
            requested_pickup_at=start,
            requested_return_at=end,
        )

    detail = str(exc_info.value.detail)
    assert "risk skoru yetersiz" in detail.lower()
