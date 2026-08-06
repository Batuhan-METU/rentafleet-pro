"""Kiralama listesinin toplu Excel (.xlsx) raporunu üreten servis.

Kiralamalar ekranındaki tabloyu (sürücü, araç, tarihler, dönem, fiyat,
fiyat farkı, teslim durumu) tek sayfada toplar. Dönem sınıflandırması
``rental_period_code`` ile yapılır; böylece Excel'deki satırlar UI'daki
sekmelerle birebir aynı kümeleri gösterir.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from django.utils import timezone

from backend.apps.rentals.models import Rental, ReturnStatus
from backend.apps.rentals.serializers import PERIOD_LABELS, rental_period_code
from backend.infrastructure.services.reporting.excel import (
    CURRENCY_FORMAT,
    build_worksheet_bytes,
)

_RETURN_TR: dict[str, str] = {
    ReturnStatus.ON_TIME: "Zamanında",
    ReturnStatus.EARLY: "Erken Teslim",
    ReturnStatus.LATE: "Geç Teslim",
}

_HEADERS: tuple[str, ...] = (
    "Sürücü",
    "Plaka",
    "Marka / Model",
    "Alış Tarihi",
    "Bırakış Tarihi",
    "Dönem",
    "Günlük Fiyat (₺)",
    "Toplam Fiyat (₺)",
    "Fiyat Farkı (₺)",
    "Teslim Durumu",
)

_NUMBER_FORMATS: dict[int, str] = {
    7: CURRENCY_FORMAT,
    8: CURRENCY_FORMAT,
    9: CURRENCY_FORMAT,
}


def _local_naive(value):
    """Excel hücresi için saat dilimi bilgisinden arındırılmış yerel tarih."""
    if value is None:
        return None
    return timezone.localtime(value).replace(tzinfo=None)


def _money(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _rental_row(rental: Rental) -> tuple[object, ...]:
    period_code = rental_period_code(rental)
    return (
        rental.driver.full_name,
        rental.vehicle.plate_number,
        f"{rental.vehicle.brand} {rental.vehicle.model}",
        _local_naive(rental.started_at),
        _local_naive(rental.ended_at),
        PERIOD_LABELS.get(period_code, period_code),
        _money(rental.daily_rate),
        _money(rental.quoted_total),
        _money(rental.price_difference),
        _RETURN_TR.get(rental.return_status, "—"),
    )


def build_rental_workbook(rentals: Iterable[Rental]) -> bytes:
    """Verilen kiralama listesi için .xlsx dosya içeriği (bytes) üretir."""
    return build_worksheet_bytes(
        "Kiralamalar",
        _HEADERS,
        (_rental_row(rental) for rental in rentals),
        number_formats=_NUMBER_FORMATS,
    )
