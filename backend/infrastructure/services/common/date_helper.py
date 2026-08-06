"""Enuygun arama tarihleri — pickup bugün+1, dropoff bugün+2 (varsayılan)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

DEFAULT_PICKUP_TIME = "10:00"
DEFAULT_DROPOFF_TIME = "10:00"
DATE_QUERY_FMT = "%Y-%m-%d"


@dataclass(frozen=True)
class RentalDateWindow:
    pickup_date: date
    dropoff_date: date
    pickup_time: str = DEFAULT_PICKUP_TIME
    dropoff_time: str = DEFAULT_DROPOFF_TIME

    @property
    def pickup_date_iso(self) -> str:
        return self.pickup_date.isoformat()

    @property
    def dropoff_date_iso(self) -> str:
        return self.dropoff_date.isoformat()


def rental_window(*, today: date | None = None) -> RentalDateWindow:
    """Sabit kural: alış yarın, dönüş ertesi gün; saatler 10:00."""
    base = today or date.today()
    return RentalDateWindow(
        pickup_date=base + timedelta(days=1),
        dropoff_date=base + timedelta(days=2),
    )


def rental_window_from_dates(pickup: date, dropoff: date) -> RentalDateWindow:
    """Belirli alış/dönüş tarihleriyle pencere oluşturur."""
    if dropoff <= pickup:
        raise ValueError("Dönüş tarihi alış tarihinden sonra olmalıdır.")
    return RentalDateWindow(pickup_date=pickup, dropoff_date=dropoff)


def parse_date_param(value: str, *, field_name: str) -> date:
    """YYYY-MM-DD query param ayrıştırıcısı."""
    try:
        return datetime.strptime(value.strip(), DATE_QUERY_FMT).date()
    except ValueError as exc:
        raise ValueError(f"{field_name} geçerli YYYY-MM-DD formatında olmalıdır.") from exc


def resolve_rental_window(
    *,
    pickup_date_param: str | None,
    dropoff_date_param: str | None,
    today: date | None = None,
) -> tuple[RentalDateWindow, bool]:
    """Query param'lardan pencere çözümler; ikinci değer varsayılan pencere mi."""
    if not pickup_date_param and not dropoff_date_param:
        window = rental_window(today=today)
        return window, True

    if not pickup_date_param or not dropoff_date_param:
        raise ValueError("baslangic_tarihi ve bitis_tarihi birlikte gönderilmelidir.")

    window = rental_window_from_dates(
        parse_date_param(pickup_date_param, field_name="baslangic_tarihi"),
        parse_date_param(dropoff_date_param, field_name="bitis_tarihi"),
    )
    default = rental_window(today=today)
    is_default = (
        window.pickup_date == default.pickup_date
        and window.dropoff_date == default.dropoff_date
    )
    return window, is_default