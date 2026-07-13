"""Teslimat durum dağılımı ve erken/geç teslimat finansal fark metrikleri."""

from __future__ import annotations

from datetime import date

from backend.apps.reservations.models import Rental, ReturnStatus

_STATUS_META = {
    ReturnStatus.ON_TIME: {"etiket": "Zamanında", "renk": "#10b981"},
    ReturnStatus.EARLY: {"etiket": "Erken", "renk": "#6366f1"},
    ReturnStatus.LATE: {"etiket": "Geç", "renk": "#f43f5e"},
}

_MONTH_NAMES = [
    "Oca", "Şub", "Mar", "Nis", "May", "Haz",
    "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
]


def _f(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _returned_rentals(company_id: int, year: int):
    return Rental.objects.filter(
        driver__company_id=company_id,
        actual_return_at__isnull=False,
        actual_return_at__year=year,
    ).exclude(return_status="")


def _available_years(company_id: int) -> list[int]:
    years = {date.today().year}
    for row in Rental.objects.filter(
        driver__company_id=company_id, actual_return_at__isnull=False
    ).dates("actual_return_at", "year"):
        years.add(row.year)
    return sorted(years, reverse=True)


def _status_distribution(rentals) -> list[dict]:
    counts = {ReturnStatus.ON_TIME: 0, ReturnStatus.EARLY: 0, ReturnStatus.LATE: 0}
    for rental in rentals:
        if rental.return_status in counts:
            counts[rental.return_status] += 1

    return [
        {
            "durum": status.value,
            "etiket": meta["etiket"],
            "adet": counts[status],
            "renk": meta["renk"],
        }
        for status, meta in _STATUS_META.items()
    ]


def _monthly_diff(rentals) -> list[dict]:
    gec_gelir = [0.0] * 12
    erken_iade = [0.0] * 12

    for rental in rentals:
        idx = rental.actual_return_at.month - 1
        diff = _f(rental.price_difference)
        if rental.return_status == ReturnStatus.LATE and diff > 0:
            gec_gelir[idx] += diff
        elif rental.return_status == ReturnStatus.EARLY and diff < 0:
            erken_iade[idx] += abs(diff)

    return [
        {
            "ay": _MONTH_NAMES[i],
            "gec_gelir": round(gec_gelir[i], 2),
            "erken_iade": round(erken_iade[i], 2),
        }
        for i in range(12)
    ]


def get_return_stats(company_id: int, year: int | None = None) -> dict:
    """Teslimat durum dağılımı + aylık erken iade / geç gelir kırılımı."""
    available_years = _available_years(company_id)
    selected_year = year if year is not None else date.today().year
    if selected_year not in available_years:
        selected_year = available_years[0]

    rentals = list(_returned_rentals(company_id, selected_year))

    gec_gelir_toplam = sum(
        _f(r.price_difference) for r in rentals if r.return_status == ReturnStatus.LATE
    )
    erken_iade_toplam = sum(
        abs(_f(r.price_difference)) for r in rentals if r.return_status == ReturnStatus.EARLY
    )

    return {
        "durum_dagilimi": _status_distribution(rentals),
        "aylik_fark": _monthly_diff(rentals),
        "ozet": {
            "toplam_teslim": len(rentals),
            "gec_gelir_toplam": round(gec_gelir_toplam, 2),
            "erken_iade_toplam": round(erken_iade_toplam, 2),
        },
        "yillar": available_years,
        "yil": selected_year,
    }
