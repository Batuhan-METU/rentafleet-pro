"""Genel toplam maliyet (§3.6) ve hibrit güncel günlük maliyet (§4).

Bu modül, 5 bileşen servisini (kredi, nakit fırsat, genel gider, sigorta,
operasyon) tek bir yerde birleştirir. §1.5 ilkesi korunur: bir bileşen
gerçekten uygulanabilir olduğu hâlde verisi eksikse (ör. finansman tipi
Kredi ama hiç kredi tahsisi girilmemiş) toplam ``None`` döner ve eksik
bileşenler ayrıca listelenir — asla sessizce 0 yazılmaz. Bir bileşen o
araç için zaten UYGULANAMAZ ise (ör. Nakit finansmanlı bir araçta "kredi"
bileşeni) bu eksik sayılmaz, 0 katkı olarak toplama girer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from backend.apps.vehicle_finance.choices import FinancingType
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.cash_opportunity_service import (
    accrued_cash_opportunity_cost,
    cash_opportunity_term_end_date,
    daily_cash_opportunity_cost,
    get_financial_profile,
)
from backend.infrastructure.services.cost_calculation.credit_interest_service import (
    accrued_credit_cost_for_vehicle,
)
from backend.infrastructure.services.cost_calculation.insurance_cost_service import (
    accrued_insurance_for_vehicle,
    current_daily_insurance_rate,
)
from backend.infrastructure.services.cost_calculation.operating_expense_service import (
    average_daily_operating_expense,
    total_operating_expense_for_vehicle,
)
from backend.infrastructure.services.cost_calculation.overhead_allocation_service import (
    accrued_overhead_for_vehicle,
    average_daily_overhead,
)
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _zero_if_none(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")


@dataclass
class CostBreakdown:
    """§3.6 — Genel Toplam Maliyet, 5 bileşen ayrı ayrı görünür şekilde."""

    credit_cost: Decimal | None
    cash_opportunity_cost: Decimal | None
    overhead_share: Decimal | None
    insurance_cost: Decimal | None
    operating_expense: Decimal
    total: Decimal | None
    cash_opportunity_term_end_date: date | None = None
    missing_components: list[str] = field(default_factory=list)


@dataclass
class HybridDailyCost:
    """§4 — Güncel Günlük Maliyet, hibrit (marjinal + ortalama) yöntem."""

    credit_daily: Decimal | None
    cash_opportunity_daily: Decimal | None
    insurance_daily: Decimal | None
    overhead_daily: Decimal | None
    operating_daily: Decimal | None
    total_daily: Decimal | None
    missing_components: list[str] = field(default_factory=list)


def _financing_missing_components(vehicle: Vehicle, credit: Decimal | None, cash: Decimal | None) -> list[str]:
    """Finansman tipine göre hangi bileşenlerin UYGULANABİLİR olduğunu, dolayısıyla
    eksikse gerçekten "eksik veri" sayılması gerektiğini belirler."""
    profile = get_financial_profile(vehicle)
    if profile is None:
        return ["financing_profile"]

    missing: list[str] = []
    if profile.financing_type in (FinancingType.LOAN, FinancingType.MIXED) and credit is None:
        missing.append("credit_allocation")
    if profile.financing_type in (FinancingType.CASH, FinancingType.MIXED) and cash is None:
        missing.append("cash_amount")
    return missing


def build_cost_breakdown(vehicle: Vehicle, as_of: date | None = None) -> CostBreakdown:
    """§3.6 — 5 bileşenin bugüne kadarki tahakkuku ve toplamı."""
    as_of = as_of or date.today()

    if vehicle.fleet_entry_date is None:
        return CostBreakdown(
            credit_cost=None,
            cash_opportunity_cost=None,
            overhead_share=None,
            insurance_cost=None,
            operating_expense=total_operating_expense_for_vehicle(vehicle, as_of),
            total=None,
            missing_components=["fleet_entry_date"],
        )

    credit = accrued_credit_cost_for_vehicle(vehicle, as_of)
    credit_cost = credit["accrued"] if credit else None
    cash_opportunity_cost = accrued_cash_opportunity_cost(vehicle, as_of)
    overhead_share = accrued_overhead_for_vehicle(vehicle, as_of)
    insurance_cost = accrued_insurance_for_vehicle(vehicle, as_of)
    operating_expense = total_operating_expense_for_vehicle(vehicle, as_of)

    missing = _financing_missing_components(vehicle, credit_cost, cash_opportunity_cost)
    if overhead_share is None:
        missing.append("overhead")
    if insurance_cost is None:
        missing.append("insurance")

    total = None
    if not missing:
        total = _round(
            _zero_if_none(credit_cost)
            + _zero_if_none(cash_opportunity_cost)
            + _zero_if_none(overhead_share)
            + _zero_if_none(insurance_cost)
            + operating_expense
        )

    return CostBreakdown(
        credit_cost=credit_cost,
        cash_opportunity_cost=cash_opportunity_cost,
        overhead_share=overhead_share,
        insurance_cost=insurance_cost,
        operating_expense=operating_expense,
        total=total,
        cash_opportunity_term_end_date=cash_opportunity_term_end_date(vehicle),
        missing_components=missing,
    )


def build_cost_breakdown_for_period(
    vehicle: Vehicle, period_start: date, period_end: date
) -> CostBreakdown:
    """Bir takvim aralığında (ör. bir yıl) tahakkuk eden maliyet.

    Hiçbir bileşenin §3.1-§3.5 formülü yeniden yazılmaz — sadece iki anlık
    görüntünün (``period_end`` ve ``period_start``'tan bir gün öncesi)
    FARKI alınır. Tüm bileşenler ``as_of``'a göre monoton artan olduğu için
    (tahakkuk asla azalmaz) fark her zaman ≥ 0'dır. Araç ``period_start``'tan
    sonra filoya girdiyse "önceki" anlık görüntü otomatik 0 çıkar — mevcut
    gün-sayım fonksiyonları bunu zaten güvenle destekliyor.

    ``before`` bileşeni ``None`` ama ``after`` biliniyorsa (ör. genel gider
    takibi şirket genelinde dönem başlangıcından SONRA başlamış — bkz.
    ``overhead_allocation_service`` "hiç kayıt yoksa boş sözlük döner"), bu
    "veri eksik" değil "dönem içinde sıfırdan başladı" demektir; ``before``
    bu durumda 0 kabul edilir. Sadece ``after`` (dönem sonu/bugün) da
    bilinmiyorsa gerçekten eksik sayılır (§1.5).
    """
    before = build_cost_breakdown(vehicle, period_start - timedelta(days=1))
    after = build_cost_breakdown(vehicle, period_end)

    def _delta(b: Decimal | None, a: Decimal | None) -> Decimal | None:
        if a is None:
            return None
        return _round(a - _zero_if_none(b))

    credit_cost = _delta(before.credit_cost, after.credit_cost)
    cash_opportunity_cost = _delta(before.cash_opportunity_cost, after.cash_opportunity_cost)
    overhead_share = _delta(before.overhead_share, after.overhead_share)
    insurance_cost = _delta(before.insurance_cost, after.insurance_cost)
    operating_expense = _round(after.operating_expense - before.operating_expense)

    missing = sorted(set(after.missing_components))

    total = None
    if not missing:
        total = _round(
            _zero_if_none(credit_cost)
            + _zero_if_none(cash_opportunity_cost)
            + _zero_if_none(overhead_share)
            + _zero_if_none(insurance_cost)
            + operating_expense
        )

    return CostBreakdown(
        credit_cost=credit_cost,
        cash_opportunity_cost=cash_opportunity_cost,
        overhead_share=overhead_share,
        insurance_cost=insurance_cost,
        operating_expense=operating_expense,
        total=total,
        cash_opportunity_term_end_date=after.cash_opportunity_term_end_date,
        missing_components=missing,
    )


def build_hybrid_daily_cost(vehicle: Vehicle, as_of: date | None = None) -> HybridDailyCost:
    """§4 — Kredi/Nakit/Sigorta MARJİNAL, Genel Gider/Operasyon ORTALAMA."""
    as_of = as_of or date.today()

    if vehicle.fleet_entry_date is None:
        return HybridDailyCost(None, None, None, None, None, None, ["fleet_entry_date"])

    credit = accrued_credit_cost_for_vehicle(vehicle, as_of)
    credit_daily = credit["marginal_daily"] if credit else None
    cash_daily = daily_cash_opportunity_cost(vehicle, as_of)
    insurance_daily = current_daily_insurance_rate(vehicle, as_of)
    overhead_daily = average_daily_overhead(vehicle, as_of)
    operating_daily = average_daily_operating_expense(vehicle, as_of)

    missing = _financing_missing_components(vehicle, credit_daily, cash_daily)
    if overhead_daily is None:
        missing.append("overhead")
    if insurance_daily is None:
        missing.append("insurance")
    if operating_daily is None:
        missing.append("operating")

    total_daily = None
    if not missing:
        total_daily = _round(
            _zero_if_none(credit_daily)
            + _zero_if_none(cash_daily)
            + _zero_if_none(insurance_daily)
            + _zero_if_none(overhead_daily)
            + _zero_if_none(operating_daily)
        )

    return HybridDailyCost(
        credit_daily=credit_daily,
        cash_opportunity_daily=cash_daily,
        insurance_daily=insurance_daily,
        overhead_daily=overhead_daily,
        operating_daily=operating_daily,
        total_daily=total_daily,
        missing_components=missing,
    )
