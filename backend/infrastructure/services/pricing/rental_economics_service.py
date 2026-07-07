"""Kiralama fiyat ekonomisi (RentA-Fleet PRO).

Mantık:
  * 1 yıllık planlama ufku (365 gün) — satış tarihi sorulmaz.
  * Yıllık yük = alış + kiraya hazırlık + (aylık işletme × 12)
  * Günlük maliyet = yıllık yük / 365
  * X günlük taban = günlük maliyet × X
  * Yakıt: dolu al–dolu bırak; ilk depo dolumu kiraya hazırlık masrafına dahil edilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from backend.models import CompetitorPrice, RentalIncome, Vehicle, VehicleFinancialProfile
from backend.infrastructure.services.common.date_helper import rental_window

PLANNING_HORIZON_DAYS: int = 365
DEFAULT_MONTHLY_MAINTENANCE: float = 2_500.0
ESTIMATED_INSURANCE_PCT_OF_PURCHASE: float = 0.045
ESTIMATED_MTV_PCT_OF_PURCHASE: float = 0.012


@dataclass(frozen=True)
class CompetitorQuote:
    """Tek bir rakip kaynağın günlük fiyat satırı."""

    kaynak: str
    gunluk_fiyat: float


@dataclass(frozen=True)
class VehicleCostCard:
    purchase_price: float
    rental_prep_cost: float
    monthly_operating: float
    annual_operating: float
    annual_burden: float
    daily_cost: float
    estimated_fields: list[str]


def _f(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def rental_days_between(pickup: date, dropoff: date) -> int:
    """Kiralama gün sayısı (en az 1)."""
    return max((dropoff - pickup).days, 1)


def competitor_quotes_for_vehicle(
    vehicle_id: int,
    *,
    pickup_date: date | None = None,
    dropoff_date: date | None = None,
) -> list[CompetitorQuote]:
    """Belirli araç ve tarih penceresi için DB'deki rakip günlük fiyatları."""
    window = rental_window()
    pickup = pickup_date or window.pickup_date
    dropoff = dropoff_date or window.dropoff_date
    rows = CompetitorPrice.objects.filter(
        vehicle_id=vehicle_id,
        pickup_date=pickup,
        dropoff_date=dropoff,
    ).order_by("source_name")
    return [
        CompetitorQuote(kaynak=row.source_name, gunluk_fiyat=float(row.daily_price))
        for row in rows
    ]


def _purchase_price(vehicle: Vehicle) -> float:
    price = _f(vehicle.purchase_price)
    if price > 0:
        return price
    try:
        return _f(vehicle.financial_profile.purchase_price)
    except VehicleFinancialProfile.DoesNotExist:
        return 0.0


def build_vehicle_cost_card(vehicle: Vehicle) -> VehicleCostCard | None:
    """Araç maliyet kartı — yıllık yük ve günlük maliyet."""
    purchase = _purchase_price(vehicle)
    if purchase <= 0:
        return None

    estimated: list[str] = []

    kasko = _f(vehicle.annual_kasko_cost)
    traffic = _f(vehicle.annual_traffic_insurance_cost)
    if kasko > 0 or traffic > 0:
        annual_insurance = kasko + traffic
    else:
        annual_insurance = _f(vehicle.annual_insurance_cost)
        if annual_insurance <= 0:
            annual_insurance = purchase * ESTIMATED_INSURANCE_PCT_OF_PURCHASE
            estimated.append("annual_kasko_cost / annual_traffic_insurance_cost")

    mtv = _f(vehicle.annual_mtv_cost)
    if mtv <= 0:
        mtv = purchase * ESTIMATED_MTV_PCT_OF_PURCHASE
        estimated.append("annual_mtv_cost")

    inspection = _f(vehicle.annual_inspection_cost)
    maintenance = _f(vehicle.estimated_monthly_maintenance)
    if maintenance <= 0:
        maintenance = DEFAULT_MONTHLY_MAINTENANCE
        estimated.append("estimated_monthly_maintenance")

    monthly = (annual_insurance / 12.0) + (mtv / 12.0) + (inspection / 12.0) + maintenance
    annual_operating = monthly * 12.0

    prep = _f(vehicle.initial_industrial_expense)
    annual_burden = purchase + prep + annual_operating
    daily = annual_burden / PLANNING_HORIZON_DAYS

    return VehicleCostCard(
        purchase_price=purchase,
        rental_prep_cost=prep,
        monthly_operating=round(monthly, 2),
        annual_operating=round(annual_operating, 2),
        annual_burden=round(annual_burden, 2),
        daily_cost=round(daily, 2),
        estimated_fields=estimated,
    )


def build_vehicle_profit_summary(vehicle: Vehicle) -> dict:
    """Tamamlanan kiralamalardan biriken net kâr (gelir − dönem maliyeti)."""
    card = build_vehicle_cost_card(vehicle)
    if card is None:
        return {
            "biriken_kar": 0.0,
            "toplam_gelir": 0.0,
            "toplam_maliyet": 0.0,
            "kiralama_sayisi": 0,
            "kiralanan_gun": 0,
            "ortalama_kar_gun": 0.0,
        }

    incomes = RentalIncome.objects.filter(vehicle=vehicle).order_by("-start_date")
    total_revenue = 0.0
    total_cost = 0.0
    rented_days = 0

    for inc in incomes:
        days = inc.total_days
        revenue = _f(inc.total_income)
        cost = card.daily_cost * days
        total_revenue += revenue
        total_cost += cost
        rented_days += days

    total_profit = total_revenue - total_cost
    return {
        "biriken_kar": round(total_profit, 2),
        "toplam_gelir": round(total_revenue, 2),
        "toplam_maliyet": round(total_cost, 2),
        "kiralama_sayisi": incomes.count(),
        "kiralanan_gun": rented_days,
        "ortalama_kar_gun": round(total_profit / rented_days, 2) if rented_days > 0 else 0.0,
    }


def build_rental_quote(
    vehicle: Vehicle,
    rental_days: int,
    *,
    market_daily_average: float | None = None,
    offered_total_price: float | None = None,
) -> dict:
    """X günlük kiralama için taban fiyat, piyasa karşılaştırması ve kâr önizlemesi."""
    days = max(int(rental_days), 1)
    card = build_vehicle_cost_card(vehicle)

    if card is None:
        return {
            "maliyet_karti_var": False,
            "mesaj": "Satın alma fiyatı girilmeden kiralama fiyatı hesaplanamaz.",
        }

    period_floor = round(card.daily_cost * days, 2)
    daily_floor = card.daily_cost
    profit_summary = build_vehicle_profit_summary(vehicle)

    market_period = None
    market_warning = None
    if market_daily_average is not None and market_daily_average > 0:
        market_period = round(market_daily_average * days, 2)
        if market_period < period_floor:
            market_warning = (
                f"Dikkat: Piyasa toplamı ({market_period:,.0f} TL) bu dönemin maliyet "
                f"tabanının ({period_floor:,.0f} TL) altında. Bu fiyattan kiralamayın."
            ).replace(",", ".")

    profit = None
    profit_daily = None
    if offered_total_price is not None and offered_total_price > 0:
        profit = round(offered_total_price - period_floor, 2)
        profit_daily = round(profit / days, 2)

    return {
        "maliyet_karti_var": True,
        "kiralanan_gun": days,
        "planlama_ufku_gun": PLANNING_HORIZON_DAYS,
        "maliyet_karti": {
            "alis_fiyati": card.purchase_price,
            "kiraya_hazirlik": card.rental_prep_cost,
            "aylik_isletme": card.monthly_operating,
            "yillik_isletme": card.annual_operating,
            "yillik_toplam_yuk": card.annual_burden,
            "tahmini_alanlar": card.estimated_fields,
        },
        "gunluk_maliyet": daily_floor,
        "donem_taban_fiyat": period_floor,
        "gunluk_taban_fiyat": daily_floor,
        "piyasa_gunluk_ortalama": market_daily_average,
        "piyasa_donem_toplam": market_period,
        "piyasa_uyarisi": market_warning,
        "teklif_toplam": offered_total_price,
        "tahmini_kar": profit,
        "tahmini_kar_gunluk": profit_daily,
        "biriken_kar": profit_summary["biriken_kar"],
        "biriken_kar_ozeti": profit_summary,
        "mesaj": (
            f"{days} günlük kiralama için maliyet tabanınız {period_floor:,.0f} TL "
            f"(günlük {daily_floor:,.0f} TL).".replace(",", ".")
        ),
    }


def build_maliyet_analizi_payload(vehicle: Vehicle) -> dict | None:
    """Araç detay / oluşturma yanıtı için özet maliyet kartı (1 günlük referans)."""
    card = build_vehicle_cost_card(vehicle)
    if card is None:
        return None
    return {
        "gunluk_maliyet": card.daily_cost,
        "yillik_toplam_yuk": card.annual_burden,
        "aylik_isletme": card.monthly_operating,
        "planlama_ufku_gun": PLANNING_HORIZON_DAYS,
        "maliyet_karti": {
            "alis_fiyati": card.purchase_price,
            "kiraya_hazirlik": card.rental_prep_cost,
            "aylik_isletme": card.monthly_operating,
            "yillik_isletme": card.annual_operating,
            "yillik_toplam_yuk": card.annual_burden,
        },
        "tahmini_alanlar": card.estimated_fields,
        "mesaj": (
            f"1 yıllık planlama ufkuyla günlük maliyet {card.daily_cost:,.0f} TL "
            f"(yıllık yük {card.annual_burden:,.0f} TL).".replace(",", ".")
        ),
    }


def get_break_even_daily(vehicle: Vehicle) -> float | None:
    """Günlük maliyet (geriye dönük uyumluluk)."""
    card = build_vehicle_cost_card(vehicle)
    return card.daily_cost if card else None
