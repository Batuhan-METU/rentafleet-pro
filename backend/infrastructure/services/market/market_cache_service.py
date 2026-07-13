"""Enuygun piyasa önbelleği — kiralama penceresi (pickup/dropoff) bazlı.

Varsayılan pencere (yarın + ertesi gün): cron ile günde bir kez doldurulur;
dashboard salt DB okur.

Gelecek tarih pencereleri: DB'de yoksa on-demand API çekimi yapılabilir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from backend.apps.enuygun.models import (
    CompetitorPrice,
    EnuygunCachedReservation,
    EnuygunMarketSnapshot,
)
from backend.infrastructure.services.common.date_helper import RentalDateWindow, rental_window
from backend.infrastructure.services.market.enuygun_service import LOCATION_LABEL, EnuygunService
from backend.infrastructure.services.sipp.segment_matcher import listing_sipp_for_reservation

logger = logging.getLogger(__name__)


def today_snapshot_date() -> date:
    return timezone.localdate()


@dataclass(frozen=True)
class MarketCacheStatus:
    snapshot_date: date
    from_cache: bool
    reservation_count: int
    fetched_at: str | None
    city: str
    pickup_date: str
    dropoff_date: str
    errors: list[str]

    def to_dict(self) -> dict:
        return {
            "snapshot_date": self.snapshot_date.isoformat(),
            "from_cache": self.from_cache,
            "reservation_count": self.reservation_count,
            "fetched_at": self.fetched_at,
            "sehir": self.city,
            "alis_tarihi": self.pickup_date,
            "donus_tarihi": self.dropoff_date,
            "hatalar": self.errors,
        }


def _status_from_snapshot(snapshot: EnuygunMarketSnapshot, *, from_cache: bool) -> MarketCacheStatus:
    return MarketCacheStatus(
        snapshot_date=snapshot.snapshot_date,
        from_cache=from_cache,
        reservation_count=snapshot.reservation_count,
        fetched_at=snapshot.fetched_at.isoformat(),
        city=snapshot.city,
        pickup_date=snapshot.pickup_date.isoformat(),
        dropoff_date=snapshot.dropoff_date.isoformat(),
        errors=[],
    )


def get_snapshot_for_window(window: RentalDateWindow) -> EnuygunMarketSnapshot | None:
    return EnuygunMarketSnapshot.objects.filter(
        pickup_date=window.pickup_date,
        dropoff_date=window.dropoff_date,
        city=LOCATION_LABEL,
    ).first()


def cached_reservations_for_snapshot(
    snapshot: EnuygunMarketSnapshot,
) -> list[dict]:
    return [
        row.to_reservation_dict()
        for row in snapshot.reservations.order_by("provider", "brand", "model")
    ]


def _parse_reservation_for_cache(reservation: dict) -> dict | None:
    vehicle = reservation.get("vehicle") or {}
    company = reservation.get("company") or {}
    price = reservation.get("price") or {}

    reference_id = (reservation.get("referenceId") or "").strip()
    if not reference_id:
        return None

    daily_raw = price.get("dailyPrice")
    if daily_raw is None:
        return None
    try:
        daily_price = Decimal(str(daily_raw))
    except (TypeError, ValueError):
        return None
    if daily_price <= 0:
        return None

    provider = (company.get("name") or reservation.get("provider") or "").strip()
    if not provider:
        return None

    return {
        "reference_id": reference_id,
        "provider": provider,
        "brand": (vehicle.get("brand") or "").strip(),
        "model": (vehicle.get("name") or "").strip(),
        "segment": listing_sipp_for_reservation(reservation),
        "vehicle_class": (vehicle.get("class") or "").strip(),
        "fuel": (vehicle.get("fuel") or "").strip(),
        "transmission": (vehicle.get("transmission") or "").strip(),
        "daily_price": daily_price,
        "currency": (price.get("currency") or "TRY").strip() or "TRY",
    }


@transaction.atomic
def _persist_snapshot(
    *,
    window: RentalDateWindow,
    reservations: list[dict],
) -> EnuygunMarketSnapshot:
    snapshot, _ = EnuygunMarketSnapshot.objects.update_or_create(
        pickup_date=window.pickup_date,
        dropoff_date=window.dropoff_date,
        city=LOCATION_LABEL,
        defaults={
            "snapshot_date": today_snapshot_date(),
            "reservation_count": 0,
        },
    )
    snapshot.reservations.all().delete()

    rows: list[EnuygunCachedReservation] = []
    for reservation in reservations:
        parsed = _parse_reservation_for_cache(reservation)
        if parsed is None:
            continue
        rows.append(EnuygunCachedReservation(snapshot=snapshot, **parsed))

    if rows:
        EnuygunCachedReservation.objects.bulk_create(rows, batch_size=500)

    snapshot.reservation_count = len(rows)
    snapshot.save(update_fields=["reservation_count", "snapshot_date"])
    return snapshot


def fetch_enuygun_market_snapshot(
    *,
    window: RentalDateWindow | None = None,
    force: bool = False,
) -> MarketCacheStatus:
    """Enuygun API'den veri çeker ve kiralama penceresi snapshot'ına yazar."""
    target = window or rental_window(today=today_snapshot_date())
    existing = get_snapshot_for_window(target)

    if existing and not force:
        return _status_from_snapshot(existing, from_cache=True)

    service = EnuygunService()
    search_result = service.fetch_all_reservations(date_window=target)
    snapshot = _persist_snapshot(window=target, reservations=search_result.reservations)

    return MarketCacheStatus(
        snapshot_date=snapshot.snapshot_date,
        from_cache=False,
        reservation_count=snapshot.reservation_count,
        fetched_at=snapshot.fetched_at.isoformat(),
        city=snapshot.city,
        pickup_date=snapshot.pickup_date.isoformat(),
        dropoff_date=snapshot.dropoff_date.isoformat(),
        errors=list(search_result.errors),
    )


def rebuild_competitor_prices_for_window(
    window: RentalDateWindow,
    *,
    company_id: int,
) -> dict:
    from backend.infrastructure.services.market.comparable_vehicle_service import rebuild_competitor_prices

    snapshot = get_snapshot_for_window(window)
    if snapshot is None:
        return {"arac_sayisi": 0, "kayit_sayisi": 0, "araclar": {}, "hatalar": []}

    reservations = cached_reservations_for_snapshot(snapshot)
    return rebuild_competitor_prices(
        reservations,
        window=window,
        company_id=company_id,
    )


def ensure_market_data_for_window(
    window: RentalDateWindow,
    *,
    on_demand: bool = False,
    company_id: int,
    force: bool = False,
) -> MarketCacheStatus:
    """Pencere verisi yoksa ``on_demand=True`` iken Enuygun'dan çeker ve CompetitorPrice üretir."""
    snapshot = get_snapshot_for_window(window)
    has_prices = CompetitorPrice.objects.filter(
        pickup_date=window.pickup_date,
        dropoff_date=window.dropoff_date,
        vehicle__company_id=company_id,
    ).exists()

    if not force and snapshot is not None and snapshot.reservation_count > 0:
        # CompetitorPrice bu şirket için zaten üretilmişse her GET'te
        # sil-yeniden-oluştur yapılmaz; yalnızca eksikse rebuild edilir.
        if not has_prices:
            rebuild_competitor_prices_for_window(window, company_id=company_id)
        return _status_from_snapshot(snapshot, from_cache=True)

    if not force and has_prices:
        if snapshot:
            return _status_from_snapshot(snapshot, from_cache=True)
        return MarketCacheStatus(
            snapshot_date=today_snapshot_date(),
            from_cache=True,
            reservation_count=0,
            fetched_at=None,
            city=LOCATION_LABEL,
            pickup_date=window.pickup_date.isoformat(),
            dropoff_date=window.dropoff_date.isoformat(),
            errors=[],
        )

    if on_demand:
        status = fetch_enuygun_market_snapshot(window=window, force=force)
        rebuild_competitor_prices_for_window(window, company_id=company_id)
        snapshot = get_snapshot_for_window(window)
        if snapshot is not None and snapshot.reservation_count > 0:
            merged = _status_from_snapshot(snapshot, from_cache=status.from_cache)
            return MarketCacheStatus(
                snapshot_date=merged.snapshot_date,
                from_cache=merged.from_cache,
                reservation_count=merged.reservation_count,
                fetched_at=merged.fetched_at,
                city=merged.city,
                pickup_date=merged.pickup_date,
                dropoff_date=merged.dropoff_date,
                errors=list(status.errors),
            )
        return status

    return MarketCacheStatus(
        snapshot_date=today_snapshot_date(),
        from_cache=False,
        reservation_count=0,
        fetched_at=None,
        city=LOCATION_LABEL,
        pickup_date=window.pickup_date.isoformat(),
        dropoff_date=window.dropoff_date.isoformat(),
        errors=[],
    )