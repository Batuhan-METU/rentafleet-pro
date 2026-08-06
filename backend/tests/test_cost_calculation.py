"""cost_calculation servis paketi — MALIYET_HESAPLAMA_METODOLOJISI birim testleri.

Üç kritik davranışı doğrular:
  * §1.4 — kova (bucket) gün sayımının HER İKİ ucu da (filoya giriş VE
    "bugün") simetrik kırpılır; projede gerçekten yaşanmış bug'ın regresyonu.
  * §3.1 — azalan bakiyeli amortisman tablosu son taksitte kalan anaparayı
    tam sıfırlar.
  * §6 — dokümanın kendi örneği: %20 hedef kâr + %50 doluluk → çarpan 2.40.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver, Gender
from backend.apps.rentals.choices import RentalStatus
from backend.apps.rentals.models import Rental
from backend.apps.vehicle_finance.choices import FinancingType, InsurancePolicyType
from backend.apps.vehicle_finance.models import (
    CompanyOverheadExpense,
    CostCalculationSettings,
    InsurancePolicy,
    Loan,
    VehicleFinancialProfile,
)
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.cash_opportunity_service import (
    accrued_cash_opportunity_cost,
    cash_opportunity_term_end_date,
    daily_cash_opportunity_cost,
)
from backend.infrastructure.services.cost_calculation.credit_interest_service import (
    generate_amortization_schedule,
)
from backend.infrastructure.services.cost_calculation.day_math import bucket_days_in_range
from backend.infrastructure.services.cost_calculation.floor_price_service import (
    build_floor_price,
)
from backend.infrastructure.services.cost_calculation.total_cost_service import (
    build_cost_breakdown,
    build_cost_breakdown_for_period,
    build_hybrid_daily_cost,
)

pytestmark = pytest.mark.django_db


# ----------------------------------------------------------------------
# §1.4 — kova gün sayımı, simetrik kırpma regresyonu
# ----------------------------------------------------------------------


def test_bucket_days_clips_only_entry_side():
    """Araç ay ortasında filoya girmiş, 'bugün' ayın çok ilerisinde."""
    days = bucket_days_in_range(
        date(2026, 1, 1), date(2026, 1, 31),
        entry_date=date(2026, 1, 15), as_of=date(2026, 6, 30),
    )
    assert days == 17  # 15..31 dahil


def test_bucket_days_clips_only_as_of_side():
    """Araç çok önceden filoda, 'bugün' bu ayın ortasında."""
    days = bucket_days_in_range(
        date(2026, 6, 1), date(2026, 6, 30),
        entry_date=date(2025, 1, 1), as_of=date(2026, 6, 10),
    )
    assert days == 10  # 1..10 dahil


def test_bucket_days_clips_both_sides_symmetrically():
    """KRİTİK TUZAK senaryosu — araç bu ay girmiş VE bugün de bu ayın içinde.

    Eski (hatalı) uygulamada sadece 'bugün' ucu kırpılıp giriş ucu unutulmuştu;
    bu, ilk (kısmi) ayın olduğundan fazla gün sayılmasına yol açıyordu.
    """
    days = bucket_days_in_range(
        date(2026, 7, 1), date(2026, 7, 31),
        entry_date=date(2026, 7, 10), as_of=date(2026, 7, 20),
    )
    assert days == 11  # 10..20 dahil — NE 31 (kırpmasız) NE 20 (tek uç kırpmalı)


# ----------------------------------------------------------------------
# §3.1 — azalan bakiyeli amortisman
# ----------------------------------------------------------------------


def test_amortization_schedule_reaches_zero_and_conserves_principal(company: Company):
    loan = Loan.objects.create(
        company=company,
        principal_amount=Decimal("1000000"),
        monthly_interest_rate=Decimal("0.035"),
        term_months=36,
        start_date=date(2026, 1, 1),
        bsmv_rate=Decimal("0.05"),
    )
    installments = generate_amortization_schedule(loan)

    assert len(installments) == 36
    assert installments[-1].remaining_principal_after == Decimal("0.00")

    total_principal = sum((row.principal_amount for row in installments), Decimal("0"))
    assert total_principal == Decimal("1000000.00")

    # Faiz azalan bakiyeyle küçülmeli: ilk taksit faizi son taksitten büyük.
    assert installments[0].interest_amount > installments[-1].interest_amount


def test_amortization_matches_real_reference_taksit_plani(company: Company):
    """Gerçek referans veriyle (`datas/Taksit_Plani.xlsx`, kredi BURGAN-
    55.000.000) formülümüzün kuruşuna kadar eşleştiğinin regresyon testi.

    NOT (veri kalitesi tuzağı): kaynak `Krediler.xlsx`'teki "Kredi Tutarı
    (Gerçek - Tüm Filo)" sütunu (55.000.000) kredinin İSMİNDEN türetilmiş
    bir etikettir, GERÇEK amortisman anaparası DEĞİLDİR — gerçek anapara
    aynı dosyanın "Kredi Faizi" sütununda (3.987.500) saklı (doğrulama:
    `Taksit_Plani.xlsx`'teki 24 taksitin "Anapara" toplamı da tam olarak
    3.987.500,02). Bu testte doğru anapara (3.987.500) kullanılıyor.
    """
    loan = Loan.objects.create(
        company=company,
        lender_name="BURGAN",
        principal_amount=Decimal("3987500"),
        monthly_interest_rate=Decimal("0.03"),
        term_months=24,
        start_date=date(2025, 5, 28),
        bsmv_rate=Decimal("0.05"),
    )
    installments = generate_amortization_schedule(loan)

    first = installments[0]
    assert first.due_date == date(2025, 6, 28)
    assert first.total_amount == Decimal("235451.57")
    assert first.principal_amount == Decimal("109845.32")
    assert first.interest_amount == Decimal("119625.00")
    assert first.bsmv_amount == Decimal("5981.25")

    second = installments[1]
    assert second.total_amount == Decimal("235451.57")
    assert second.principal_amount == Decimal("113305.45")
    assert second.interest_amount == Decimal("116329.64")
    assert second.bsmv_amount == Decimal("5816.48")


# ----------------------------------------------------------------------
# §6 — doluluk-düzeltmeli kurtaran fiyat, dokümanın kendi örneği
# ----------------------------------------------------------------------


def _aware(d: date) -> datetime:
    # Öğlen kullanılır ki yerel saat dilimi (Europe/Istanbul, UTC+3) UTC'ye
    # çevrilirken takvim günü kaymasın (gece yarısı kullanılsaydı kayardı).
    return timezone.make_aware(datetime.combine(d, time(12, 0)))


def test_floor_price_matches_doc_worked_example(company: Company):
    """Doküman §6: %20 hedef kâr, %50 doluluk → çarpan tam olarak 2.40."""
    entry_date = date.today() - timedelta(days=9)  # + bugün = 10 günlük filo penceresi
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34FLR001",
        brand="Renault",
        model="Clio",
        production_year=2024,
        purchase_price=Decimal("500000"),
        fleet_entry_date=entry_date,
    )
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle,
        purchase_date=entry_date,
        purchase_price=Decimal("500000"),
        financing_type=FinancingType.CASH,
        cash_financed_amount=Decimal("500000"),
    )
    InsurancePolicy.objects.create(
        vehicle=vehicle,
        policy_type=InsurancePolicyType.COMPREHENSIVE,
        amount=Decimal("20000"),
        start_date=entry_date,
        end_date=entry_date + timedelta(days=365),
    )
    CompanyOverheadExpense.objects.create(
        company=company, expense_date=date.today(), amount=Decimal("1000")
    )

    driver = Driver.objects.create(
        company=company,
        first_name="Test",
        last_name="Sürücü",
        national_id="11122233344",
        gender=Gender.MALE,
        birth_date=date(1990, 1, 1),
        phone="05551234567",
        email="test@example.com",
        license_number="AB123456",
        license_class="B",
        city="Ankara",
    )
    # Filonun 10 günlük penceresinde tam 5 gün (%50) kirada — ilk gün dahil.
    Rental.objects.create(
        driver=driver,
        vehicle=vehicle,
        status=RentalStatus.COMPLETED,
        started_at=_aware(entry_date),
        ended_at=_aware(entry_date + timedelta(days=4)),
        actual_return_at=_aware(entry_date + timedelta(days=4)),
        start_km=0,
    )

    hybrid = build_hybrid_daily_cost(vehicle)
    assert hybrid.missing_components == []

    floor = build_floor_price(vehicle)
    assert floor.occupancy_rate == Decimal("0.5000")
    assert floor.target_profit_margin == Decimal("0.2000")
    assert floor.multiplier == Decimal("2.4000")
    assert hybrid.total_daily is not None
    assert floor.daily_floor_price == (hybrid.total_daily * Decimal("2.4")).quantize(Decimal("0.01"))


# ----------------------------------------------------------------------
# §3.2 — nakit fırsat maliyeti vadesi (kullanıcıyla netleştirilmiş karar:
# kredinin kendi vadesiyle bitmesine paralel, nakit de bir vade sonunda durur)
# ----------------------------------------------------------------------


@pytest.fixture
def cash_vehicle(company: Company) -> Vehicle:
    entry_date = date(2020, 2, 11)
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34CSH001",
        brand="Fiat",
        model="Egea",
        production_year=2020,
        purchase_price=Decimal("300000"),
        fleet_entry_date=entry_date,
    )
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle,
        purchase_date=entry_date,
        purchase_price=Decimal("300000"),
        financing_type=FinancingType.CASH,
        cash_financed_amount=Decimal("300000"),
    )
    return vehicle


def test_cash_opportunity_term_end_date_equals_entry_plus_term_months(cash_vehicle: Vehicle):
    settings_row, _ = CostCalculationSettings.objects.get_or_create(company=cash_vehicle.company)
    assert settings_row.cash_opportunity_term_months == 36  # güncel varsayılan: 3 yıl

    assert cash_opportunity_term_end_date(cash_vehicle) == date(2023, 2, 11)


def test_daily_cash_opportunity_cost_becomes_zero_after_term(cash_vehicle: Vehicle):
    before_term = daily_cash_opportunity_cost(cash_vehicle, as_of=date(2023, 2, 10))
    assert before_term is not None
    assert before_term > 0

    at_term_end = daily_cash_opportunity_cost(cash_vehicle, as_of=date(2023, 2, 11))
    assert at_term_end == Decimal("0.00")

    long_after = daily_cash_opportunity_cost(cash_vehicle, as_of=date(2026, 7, 31))
    assert long_after == Decimal("0.00")


def test_daily_cash_opportunity_cost_uses_leap_year_divisor(cash_vehicle: Vehicle):
    """Türk mevduat faizi kuralı: artık yılda bölen 366, değilse 365 —
    aynı oran/tutar, artık yılda biraz daha düşük günlük getiri verir."""
    # 2020 artık yıl (366 gün) — 300.000 × %40 / 366.
    leap_year_daily = daily_cash_opportunity_cost(cash_vehicle, as_of=date(2020, 2, 12))
    assert leap_year_daily == (Decimal("300000") * Decimal("0.40") / Decimal(366)).quantize(Decimal("0.01"))

    # 2021 artık yıl değil (365 gün) — aynı oran/tutar, bölen farklı.
    non_leap_year_daily = daily_cash_opportunity_cost(cash_vehicle, as_of=date(2021, 6, 1))
    assert non_leap_year_daily == (Decimal("300000") * Decimal("0.40") / Decimal(365)).quantize(Decimal("0.01"))

    assert leap_year_daily < non_leap_year_daily


def test_accrued_cash_opportunity_cost_freezes_at_term_end(cash_vehicle: Vehicle):
    """Kredinin taksitleri bitince faizi kesildiği gibi, nakit fırsat maliyeti
    de vade tarihinden sonra artık artmamalı — tahakkuk orada donmalı."""
    accrued_at_term = accrued_cash_opportunity_cost(cash_vehicle, as_of=date(2023, 2, 11))
    accrued_long_after = accrued_cash_opportunity_cost(cash_vehicle, as_of=date(2026, 7, 31))
    assert accrued_at_term == accrued_long_after

    # Vade öncesi bir gün, vade tarihinden az ama sıfırdan büyük olmalı.
    accrued_before_term = accrued_cash_opportunity_cost(cash_vehicle, as_of=date(2023, 2, 10))
    assert accrued_before_term is not None
    assert accrued_at_term is not None
    assert Decimal("0") < accrued_before_term < accrued_at_term

    # Donan tutar, dönemi (2020-02-11 hariç → 2023-02-11 dahil) takvim
    # yılına göre bölüp her yılın kendi 365/366 böleniyle hesaplanan
    # (Anapara × Oran × Gün)/36500|36600 katkılarının toplamına eşit olmalı
    # — sabit bir "günlük oran × toplam gün" ÇARPIMINA eşit OLMAMALI, çünkü
    # dönem içinde 2020 (artık yıl, 366 gün) ile 2021-2023 (365 gün) karışık.
    days_by_year = {2020: 324, 2021: 365, 2022: 365, 2023: 42}
    assert sum(days_by_year.values()) == (date(2023, 2, 11) - date(2020, 2, 11)).days
    expected = sum(
        (
            Decimal("300000") * Decimal("0.40") * Decimal(days) / Decimal(366 if year == 2020 else 365)
            for year, days in days_by_year.items()
        ),
        start=Decimal("0"),
    )
    assert accrued_at_term == expected.quantize(Decimal("0.01"))


# ----------------------------------------------------------------------
# build_cost_breakdown_for_period — Araç Detayı "Gelir & Gider Özeti"nin
# yıla göre kırılımı, iki lifetime anlık görüntüsünün farkı olarak
# ----------------------------------------------------------------------


def test_cost_breakdown_for_period_sums_to_full_lifetime_total(company: Company):
    entry_date = date(2024, 1, 1)
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34PRD001",
        brand="Renault",
        model="Clio",
        production_year=2024,
        purchase_price=Decimal("200000"),
        fleet_entry_date=entry_date,
    )
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle,
        purchase_date=entry_date,
        purchase_price=Decimal("200000"),
        financing_type=FinancingType.CASH,
        cash_financed_amount=Decimal("200000"),
    )
    InsurancePolicy.objects.create(
        vehicle=vehicle,
        policy_type=InsurancePolicyType.COMPREHENSIVE,
        amount=Decimal("36500"),  # günlük tam 100,00
        start_date=entry_date,
        end_date=entry_date + timedelta(days=800),
    )
    for offset, amount in ((0, "1000"), (180, "1500"), (360, "1200")):
        CompanyOverheadExpense.objects.create(
            company=company,
            expense_date=entry_date + timedelta(days=offset),
            amount=Decimal(amount),
        )

    as_of_total = entry_date + timedelta(days=500)
    split_point = entry_date + timedelta(days=250)

    lifetime = build_cost_breakdown(vehicle, as_of_total)
    assert lifetime.missing_components == []

    period1 = build_cost_breakdown_for_period(vehicle, entry_date, split_point)
    period2 = build_cost_breakdown_for_period(
        vehicle, split_point + timedelta(days=1), as_of_total
    )
    assert period1.missing_components == []
    assert period2.missing_components == []

    # Parçaların toplamı bütüne eşit olmalı (§3.6 tutarlılığı) — küçük bir
    # yuvarlama payı (iki ayrı _round çağrısından) toleransla kabul edilir.
    for field in ("cash_opportunity_cost", "overhead_share", "insurance_cost"):
        combined = getattr(period1, field) + getattr(period2, field)
        assert abs(combined - getattr(lifetime, field)) <= Decimal("0.02")
    assert period1.operating_expense is not None
    assert period2.operating_expense is not None
    assert lifetime.operating_expense is not None
    assert (
        abs(
            (period1.operating_expense + period2.operating_expense)
            - lifetime.operating_expense
        )
        <= Decimal("0.02")
    )
    assert period1.total is not None
    assert period2.total is not None
    assert lifetime.total is not None
    assert abs((period1.total + period2.total) - lifetime.total) <= Decimal("0.05")


def test_cost_breakdown_for_period_zero_before_fleet_entry_not_missing(company: Company):
    """Araç henüz filoya girmeden önceki bir dönem — bileşenler gerçek 0
    olmalı (§1.5: bu, veri eksikliği değil, henüz var olmama durumu)."""
    entry_date = date(2024, 6, 1)
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34PRD002",
        brand="Renault",
        model="Clio",
        production_year=2024,
        purchase_price=Decimal("200000"),
        fleet_entry_date=entry_date,
    )
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle,
        purchase_date=entry_date,
        purchase_price=Decimal("200000"),
        financing_type=FinancingType.CASH,
        cash_financed_amount=Decimal("200000"),
    )
    InsurancePolicy.objects.create(
        vehicle=vehicle,
        policy_type=InsurancePolicyType.COMPREHENSIVE,
        amount=Decimal("36500"),
        start_date=entry_date,
        end_date=entry_date + timedelta(days=800),
    )
    # Genel gider takibi araç filoya girmeden ÖNCE de mevcut (şirket geneli).
    CompanyOverheadExpense.objects.create(
        company=company, expense_date=date(2023, 1, 1), amount=Decimal("1000")
    )

    result = build_cost_breakdown_for_period(
        vehicle, date(2023, 6, 1), date(2023, 12, 31)
    )
    assert result.missing_components == []
    assert result.cash_opportunity_cost == Decimal("0.00")
    assert result.overhead_share == Decimal("0.00")
    assert result.insurance_cost == Decimal("0.00")
    assert result.operating_expense == Decimal("0.00")
    assert result.total == Decimal("0.00")


def test_cost_breakdown_for_period_component_starting_mid_period_is_zero_not_missing(
    company: Company,
):
    """Genel gider takibi dönem İÇİNDE başlamışsa (ör. şirket muhasebe
    kaydına yeni geçti), dönem başı 'veri eksik' değil 'henüz sıfırdı'
    kabul edilir — aksi halde tüm dönem yanlışlıkla 'Veri eksik' görünür
    (34PAF884 ile keşfedilen gerçek senaryo)."""
    entry_date = date(2020, 1, 1)
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34PRD003",
        brand="Renault",
        model="Clio",
        production_year=2020,
        purchase_price=Decimal("200000"),
        fleet_entry_date=entry_date,
    )
    VehicleFinancialProfile.objects.create(
        vehicle=vehicle,
        purchase_date=entry_date,
        purchase_price=Decimal("200000"),
        financing_type=FinancingType.CASH,
        cash_financed_amount=Decimal("200000"),
    )
    InsurancePolicy.objects.create(
        vehicle=vehicle,
        policy_type=InsurancePolicyType.COMPREHENSIVE,
        amount=Decimal("36500"),
        start_date=entry_date,
        end_date=entry_date + timedelta(days=3000),
    )
    # İlk genel gider kaydı, test edilen dönemin (2021) TAM ORTASINDA.
    CompanyOverheadExpense.objects.create(
        company=company, expense_date=date(2021, 6, 1), amount=Decimal("1000")
    )

    before_snapshot = build_cost_breakdown(vehicle, date(2020, 12, 31))
    assert "overhead" in before_snapshot.missing_components
    assert before_snapshot.overhead_share is None

    after_snapshot = build_cost_breakdown(vehicle, date(2021, 12, 31))
    assert "overhead" not in after_snapshot.missing_components
    assert after_snapshot.overhead_share is not None

    result = build_cost_breakdown_for_period(vehicle, date(2021, 1, 1), date(2021, 12, 31))
    assert "overhead" not in result.missing_components
    assert result.overhead_share == after_snapshot.overhead_share
    assert result.total is not None
