"""Enuygun arama tarihleri — pickup bugün+1, dropoff bugün+2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

DEFAULT_PICKUP_TIME = "10:00"
DEFAULT_DROPOFF_TIME = "10:00"


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
