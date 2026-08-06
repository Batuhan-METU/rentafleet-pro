"""Şirket ev sayfası metrikleri — filo durumu + yıllık finansal KPI."""

from __future__ import annotations

from datetime import date

from django.core.cache import cache
from django.db.models import Sum

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import (
    RentalIncome,
    VehicleExpense,
)
from backend.apps.vehicles.models import (
    Vehicle,
    VehicleStatus,
)
from backend.common.multitenancy_tools.branding import company_branding_payload
from backend.infrastructure.services.cost_calculation.rental_economics_service import (
    current_daily_cost,
)


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
    rented = available = maintenance = 0
    for vehicle in vehicles:
        if vehicle.status == VehicleStatus.RENTED:
            rented += 1
        elif vehicle.status == VehicleStatus.AVAILABLE:
            available += 1
        elif vehicle.status == VehicleStatus.MAINTENANCE:
            maintenance += 1
    return {
        "toplam": len(vehicles),
        "kirada": rented,
        "musait": available,
        "bakimda": maintenance,
    }


# Şirket/yıl bazlı KPI hesabı, gelir kayıtları üzerinde araç başına günlük
# maliyet çıkaran ağır bir döngü (bkz. aşağıdaki fonksiyon) — genel bakış
# sayfası her açıldığında yeniden hesaplanmasın diye kısa süreli (60 sn)
# önbelleğe alınır. TTL kısa tutulur: veri hiçbir zaman bir dakikadan fazla
# bayat kalmaz, ayrı bir "önbelleği geçersiz kıl" mekanizması gerekmez.
YEAR_METRICS_CACHE_TTL_SECONDS = 60


def _year_metrics(company_id: int, year: int) -> dict:
    cache_key = f"overview:year_metrics:{company_id}:{year}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    result = _compute_year_metrics(company_id, year)
    cache.set(cache_key, result, timeout=YEAR_METRICS_CACHE_TTL_SECONDS)
    return result


def _compute_year_metrics(company_id: int, year: int) -> dict:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    incomes = RentalIncome.objects.filter(
        vehicle__company_id=company_id,
        start_date__gte=year_start,
        start_date__lte=year_end,
    ).select_related("vehicle")

    annual_revenue = 0.0
    annual_cost = 0.0
    rented_days = 0
    as_of = min(year_end, date.today())
    # Aynı araç yıl içinde birden fazla gelir kaydına sahip olabilir; günlük
    # maliyeti araç başına bir kez hesaplayıp önbelleklemek genel gider
    # dağıtımının (tüm filoyu tarayan) tekrar tekrar çalışmasını önler.
    daily_cost_cache: dict[int, float | None] = {}
    missing_cost_vehicle_ids: set[int] = set()

    for income in incomes:
        revenue = _f(income.total_income)
        days = income.total_days or 0
        annual_revenue += revenue
        rented_days += days

        vehicle_id = income.vehicle_id
        if vehicle_id not in daily_cost_cache:
            daily = current_daily_cost(income.vehicle, as_of)
            daily_cost_cache[vehicle_id] = _f(daily) if daily is not None else None
        daily_cost = daily_cost_cache[vehicle_id]

        if daily_cost is not None:
            annual_cost += daily_cost * days
        else:
            # §1.5 — maliyet bilinmiyorsa bu gelir satırının Yıllık Gider'e
            # katkısı da bilinmiyor demektir; sessizce maliyet=0 varsayılmaz.
            missing_cost_vehicle_ids.add(vehicle_id)

    year_expenses = _f(
        VehicleExpense.objects.filter(
            vehicle__company_id=company_id,
            expense_date__gte=year_start,
            expense_date__lte=year_end,
        ).aggregate(total=Sum("amount"))["total"]
    )
    # Net Kar, Yıllık Gider'den TÜRETİLMEZ — aksi halde operasyon gideri (zaten
    # current_daily_cost'un bir bileşeni olarak Yıllık Gider'in içinde) burada
    # ikinci kez düşülmüş olurdu. Net Kar; sadece brüt gelir ile o yıl
    # gerçekleşmiş nakit operasyon giderinin (VehicleExpense) basit farkıdır.
    net_profit = annual_revenue - year_expenses

    return {
        "yillik_gider": round(annual_cost, 2),
        "yillik_gelir": round(annual_revenue, 2),
        "net_kar": round(net_profit, 2),
        "kiralama_sayisi": incomes.count(),
        "kiralanan_gun": rented_days,
        "eksik_maliyet_arac_sayisi": len(missing_cost_vehicle_ids),
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
            "anahtar": "yillik_gider",
            "etiket": "Yıllık Gider",
            "deger": year_metrics["yillik_gider"],
            "birim": "TL",
            "vurgu": True,
            "renk": "orange",
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

    fleet_status = _fleet_status(vehicles)
    year_metrics = _year_metrics(company_id, selected_year)
    monthly_revenue = _monthly_revenue(company_id, selected_year)

    return {
        "sirket": {
            "id": company.pk,
            "ticari_unvan": branding["display_name"],
            "logo_url": branding["logo_url"],
        },
        "filo_durumu": fleet_status,
        "istatistikler": _build_stat_cards(year_metrics),
        "grafik": {
            "aylik_gelir": monthly_revenue,
        },
        "yillar": available_years,
        "yil": selected_year,
    }