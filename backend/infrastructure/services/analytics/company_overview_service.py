"""Şirket ev sayfası metrikleri — filo durumu + yıllık finansal KPI."""

from __future__ import annotations

from datetime import date

from django.db.models import Sum

from backend.infrastructure.services.pricing.rental_economics_service import (
    build_vehicle_cost_card,
)
from backend.apps.floor_pricing.models import (
    RentalIncome,
    VehicleExpense,
)
from backend.apps.companies.models import Company
from backend.apps.vehicles.models import (
    Vehicle,
    VehicleStatus,
)
from backend.common.multitenancy_tools.branding import company_branding_payload


def _f(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _available_years(company_id: int) -> list[int]:
    years = {date.today().year}
    company = Company.objects.get(pk=company_id)
    years.add(company.created_at.year)
    for row in RentalIncome.objects.filter(vehicle__company_id=company_id).dates(
        "start_date", "year"
    ):
        years.add(row.year)
    return sorted(years, reverse=True)


def _fleet_status(vehicles: list[Vehicle]) -> dict:
    kirada = musait = bakimda = 0
    for vehicle in vehicles:
        if vehicle.status == VehicleStatus.RENTED:
            kirada += 1
        elif vehicle.status == VehicleStatus.AVAILABLE:
            musait += 1
        elif vehicle.status == VehicleStatus.MAINTENANCE:
            bakimda += 1
    return {
        "toplam": len(vehicles),
        "kirada": kirada,
        "musait": musait,
        "bakimda": bakimda,
    }


def _year_metrics(company_id: int, year: int) -> dict:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    incomes = RentalIncome.objects.filter(
        vehicle__company_id=company_id,
        start_date__gte=year_start,
        start_date__lte=year_end,
    ).select_related("vehicle")

    yillik_gelir = 0.0
    net_kazanc = 0.0
    kiralanan_gun = 0

    for income in incomes:
        revenue = _f(income.total_income)
        days = income.total_days or 0
        yillik_gelir += revenue
        kiralanan_gun += days
        card = build_vehicle_cost_card(income.vehicle)
        if card:
            net_kazanc += revenue - card.daily_cost * days
        else:
            net_kazanc += revenue

    year_expenses = _f(
        VehicleExpense.objects.filter(
            vehicle__company_id=company_id,
            expense_date__gte=year_start,
            expense_date__lte=year_end,
        ).aggregate(total=Sum("amount"))["total"]
    )
    net_kar = net_kazanc - year_expenses

    return {
        "net_kazanc": round(net_kazanc, 2),
        "yillik_gelir": round(yillik_gelir, 2),
        "net_kar": round(net_kar, 2),
        "kiralama_sayisi": incomes.count(),
        "kiralanan_gun": kiralanan_gun,
    }


def _monthly_revenue(company_id: int, year: int) -> list[dict]:
    """Seçili yıl için aylık gelir serisi (grafik)."""
    months = [0.0] * 12
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    incomes = RentalIncome.objects.filter(
        vehicle__company_id=company_id,
        start_date__gte=year_start,
        start_date__lte=year_end,
    )

    month_names = [
        "Oca", "Şub", "Mar", "Nis", "May", "Haz",
        "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
    ]

    for income in incomes:
        idx = income.start_date.month - 1
        months[idx] += _f(income.total_income)

    return [
        {"ay": month_names[i], "gelir": round(months[i], 2)}
        for i in range(12)
    ]


def _build_stat_cards(year_metrics: dict) -> list[dict]:
    return [
        {
            "anahtar": "net_kazanc",
            "etiket": "Net Kazanç",
            "deger": year_metrics["net_kazanc"],
            "birim": "TL",
            "vurgu": True,
            "renk": "violet",
        },
        {
            "anahtar": "yillik_gelir",
            "etiket": "Yıllık Gelir",
            "deger": year_metrics["yillik_gelir"],
            "birim": "TL",
            "renk": "cyan",
        },
        {
            "anahtar": "net_kar",
            "etiket": "Net Kar",
            "deger": year_metrics["net_kar"],
            "birim": "TL",
            "vurgu": True,
            "renk": "emerald",
        },
        {
            "anahtar": "kiralama_sayisi",
            "etiket": "Toplam Kiralama",
            "deger": year_metrics["kiralama_sayisi"],
            "birim": "adet",
            "renk": "amber",
        },
        {
            "anahtar": "kiralanan_gun",
            "etiket": "Kiralanan Gün",
            "deger": year_metrics["kiralanan_gun"],
            "birim": "gün",
            "renk": "rose",
        },
    ]


def get_company_overview(company_id: int, year: int | None = None) -> dict:
    """Şirket künyesi, filo durumu ve yıllık finansal KPI listesini döndürür."""
    company = Company.objects.get(pk=company_id)
    branding = company_branding_payload(company)
    vehicles = list(Vehicle.objects.filter(company_id=company_id))

    available_years = _available_years(company_id)
    selected_year = year if year is not None else date.today().year
    if selected_year not in available_years:
        selected_year = available_years[0]

    filo = _fleet_status(vehicles)
    year_metrics = _year_metrics(company_id, selected_year)
    monthly_revenue = _monthly_revenue(company_id, selected_year)

    return {
        "sirket": {
            "id": company.pk,
            "ticari_unvan": branding["display_name"],
            "logo_url": branding["logo_url"],
        },
        "filo_durumu": filo,
        "istatistikler": _build_stat_cards(year_metrics),
        "grafik": {
            "aylik_gelir": monthly_revenue,
        },
        "yillar": available_years,
        "yil": selected_year,
    }