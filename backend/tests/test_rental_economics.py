"""Kiralama maliyet ekonomisi (rental_economics_service) — v2 gerçek maliyet motoru.

v1'in (yıllık yük / 365, tahmini alan yüzdeleri) testleri kaldırılmıştır —
o formül tamamen kaldırıldı. Bunun yerine ``current_daily_cost``/
``build_cost_analysis_payload``'ın gerçek finansman/sigorta/genel gider
verisiyle doğru toplandığı, herhangi bir bileşen eksikken toplamın
sessizce 0 değil ``None`` (§1.5) döndüğü ve ``rental_days_between``'ın
değişmediği doğrulanır.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.choices import ExpenseCategory, FinancingType, InsurancePolicyType
from backend.apps.vehicle_finance.models import (
    CompanyOverheadExpense,
    InsurancePolicy,
    VehicleExpense,
    VehicleFinancialProfile,
)
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.rental_economics_service import (
    build_cost_analysis_payload,
    build_vehicle_yearly_summary,
    current_daily_cost,
    rental_days_between,
)
from backend.infrastructure.services.cost_calculation.total_cost_service import (
    build_cost_breakdown,
    build_hybrid_daily_cost,
)

pytestmark = pytest.mark.django_db


def _vehicle(company: Company, **overrides) -> Vehicle:
    defaults = dict(
        company=company,
        plate_number="34TEST01",
        brand="Renault",
        model="Clio",
        production_year=2022,
        purchase_price=Decimal("500000"),
        fleet_entry_date=date.today() - timedelta(days=100),
    )
    defaults.update(overrides)
    return Vehicle.objects.create(**defaults)


def test_no_fleet_entry_date_means_no_daily_cost(company: Company):
    vehicle = _vehicle(company, fleet_entry_date=None)
    assert current_daily_cost(vehicle) is None
    assert build_cost_analysis_payload(vehicle) is None

    breakdown = build_cost_breakdown(vehicle)
    assert breakdown.total is None
    assert "fleet_entry_date" in breakdown.missing_components


def test_missing_financing_profile_blocks_total(company: Company):
    # fleet_entry_date var ama hiç VehicleFinancialProfile yok — finansman
    # tamamen bilinmiyor, toplam sessizce 0 değil None olmalı.
    vehicle = _vehicle(company)
    breakdown = build_cost_breakdown(vehicle)
    assert breakdown.total is None
    assert "financing_profile" in breakdown.missing_components
    # Operasyon gideri (kayıt yoksa gerçekten 0'dır, ayrı bir eksik değildir).
    assert breakdown.operating_expense == Decimal("0.00")


def test_fully_configured_cash_vehicle_daily_cost_matches_hand_calculation(company: Company):
    """Nakit + sigorta + genel gider tam dolu bir araç için hibrit günlük
    maliyeti, dokümandaki formüllerle elle hesaplanan değerle birebir
    örtüşmeli."""
    vehicle = _vehicle(company, purchase_price=Decimal("500000"))
    assert vehicle.fleet_entry_date is not None
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle,
        purchase_date=vehicle.fleet_entry_date,
        purchase_price=Decimal("500000"),
        financing_type=FinancingType.CASH,
        cash_financed_amount=Decimal("500000"),
    )
    InsurancePolicy.objects.create(
        vehicle=vehicle,
        policy_type=InsurancePolicyType.COMPREHENSIVE,
        amount=Decimal("20000"),
        start_date=vehicle.fleet_entry_date,
        end_date=vehicle.fleet_entry_date + timedelta(days=365),
    )
    CompanyOverheadExpense.objects.create(
        company=company,
        expense_date=date.today(),
        amount=Decimal("1000"),
    )

    hybrid = build_hybrid_daily_cost(vehicle)
    assert hybrid.missing_components == []

    # §3.2 — nakit fırsat maliyeti: 500.000 × %40/365 (bugün artık yıl değil).
    expected_cash = (Decimal("500000") * Decimal("0.40") / Decimal(365)).quantize(Decimal("0.01"))
    assert hybrid.cash_opportunity_daily == expected_cash

    # §3.4 — sigorta günlük oranı: 20.000/365.
    expected_insurance = (Decimal("20000") / Decimal(365)).quantize(Decimal("0.01"))
    assert hybrid.insurance_daily == expected_insurance

    # §3.3 — genel gider: tek araç = tek başına havuz, tek günlük gider
    # kaydı / (bugün - filoya giriş) gün sayısı.
    assert hybrid.overhead_daily == Decimal("10.00")
    assert hybrid.operating_daily == Decimal("0.00")
    assert hybrid.credit_daily is None  # Nakit finansmanlı araçta kredi bileşeni yok.

    expected_total = expected_cash + expected_insurance + Decimal("10.00")
    assert hybrid.total_daily == expected_total

    analysis = build_cost_analysis_payload(vehicle)
    assert analysis is not None
    assert analysis["daily_cost"] == expected_total


def test_rental_days_between_is_at_least_one():
    assert rental_days_between(date(2026, 7, 10), date(2026, 7, 10)) == 1
    assert rental_days_between(date(2026, 7, 10), date(2026, 7, 15)) == 5


def test_yearly_summary_operating_income_excludes_future_dated_and_other_years(company: Company):
    """"Gelir Kompozisyonu"nun Operasyon segmenti — sadece SEÇİLİ YIL içinde
    VE bugüne kadar (ileri tarihli değil) gerçekleşmiş income_amount'lar
    sayılır; bu, operating_expense ile BİREBİR aynı dönem sınırını kullanır
    (bkz. VehicleOperationalExpenseModal.vue'daki eşdeğer client-side fix)."""
    vehicle = _vehicle(company, fleet_entry_date=date(2024, 1, 1))
    this_year = date.today().year

    # Bu yıl, bugüne kadar → sayılır.
    VehicleExpense.objects.create(
        vehicle=vehicle,
        category=ExpenseCategory.VEHICLE_DAMAGE_REPAIR,
        amount="8000.00",
        income_amount="3000.00",
        expense_date=date.today(),
    )
    # Bu yıl ama ileri tarihli (henüz gerçekleşmedi) → SAYILMAZ.
    VehicleExpense.objects.create(
        vehicle=vehicle,
        category=ExpenseCategory.VEHICLE_DAMAGE_REPAIR,
        amount="5000.00",
        income_amount="2000.00",
        expense_date=date.today() + timedelta(days=30),
    )
    # Geçen yıl → SAYILMAZ.
    VehicleExpense.objects.create(
        vehicle=vehicle,
        category=ExpenseCategory.VEHICLE_DAMAGE_REPAIR,
        amount="1000.00",
        income_amount="500.00",
        expense_date=date(this_year - 1, 6, 1),
    )

    summary = build_vehicle_yearly_summary(vehicle, this_year)

    assert summary["operating_income"] == 3000.00
    assert summary["cost_breakdown"]["operating_expense"] == Decimal("8000.00")
