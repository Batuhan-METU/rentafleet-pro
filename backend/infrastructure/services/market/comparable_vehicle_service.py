"""Enuygun piyasa fiyatları — CompetitorPrice üretimi (API'den bağımsız okuma katmanı)."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from backend.apps.enuygun.models import CompetitorPrice
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.common.date_helper import RentalDateWindow, rental_window
from backend.infrastructure.services.market.reservation_filter import MarketSegmentReport, ReservationFilter

logger = logging.getLogger(__name__)


def _persist_report(
    vehicle: Vehicle,
    report: MarketSegmentReport,
    *,
    window: RentalDateWindow,
) -> int:
    seen_refs: set[str] = set()
    saved = 0

    with transaction.atomic():
        CompetitorPrice.objects.filter(
            vehicle=vehicle,
            pickup_date=window.pickup_date,
            dropoff_date=window.dropoff_date,
        ).delete()

        for row in report.matched_vehicles:
            ref = (row.reference_id or "").strip()
            if not ref or ref in seen_refs:
                continue
            seen_refs.add(ref)

            CompetitorPrice.objects.create(
                vehicle=vehicle,
                provider_name=row.provider,
                source_name=row.provider,
                external_reference=ref,
                daily_price=Decimal(str(row.daily_price)),
                sipp_code=row.segment[:4] if row.segment else report.matched_segment,
                similar_vehicle=f"{row.brand} {row.model}".strip(),
                pickup_date=window.pickup_date,
                dropoff_date=window.dropoff_date,
            )
            saved += 1

    return saved


def rebuild_competitor_prices(
    reservations: list[dict],
    *,
    window: RentalDateWindow,
    company_id: int,
) -> dict:
    reservation_filter = ReservationFilter()
    vehicle_count = 0
    row_count = 0
    per_vehicle: dict[str, dict] = {}
    sync_errors: list[str] = []

    vehicle_qs = Vehicle.objects.filter(company_id=company_id).order_by("plate_number")
    for vehicle in vehicle_qs:
        try:
            report = reservation_filter.build_report(reservations, vehicle)
            row_count += _persist_report(vehicle, report, window=window)
            vehicle_count += 1
            per_vehicle[str(vehicle.pk)] = report.to_dict()
        except Exception as exc:
            msg = f"{vehicle.plate_number} senkron hatası: {exc}"
            logger.exception(msg)
            sync_errors.append(msg)

    return {
        "arac_sayisi": vehicle_count,
        "kayit_sayisi": row_count,
        "araclar": per_vehicle,
        "hatalar": sync_errors,
    }


def sync_fleet_market_prices(
    *,
    force: bool = True,
    window: RentalDateWindow | None = None,
    company_id: int,
) -> dict:
    from backend.infrastructure.services.market.market_cache_service import (
        fetch_enuygun_market_snapshot,
        rebuild_competitor_prices_for_window,
    )

    target = window or rental_window()
    cache_status = fetch_enuygun_market_snapshot(window=target, force=force)
    rebuild = rebuild_competitor_prices_for_window(target, company_id=company_id)

    return {
        "arac_sayisi": rebuild["arac_sayisi"],
        "kayit_sayisi": rebuild["kayit_sayisi"],
        "toplam_rezervasyon": cache_status.reservation_count,
        "cekilen_rezervasyon": cache_status.reservation_count,
        "onbellek": cache_status.to_dict(),
        "hatalar": list(cache_status.errors) + list(rebuild.get("hatalar", [])),
        "araclar": rebuild["araclar"],
        "alis_tarihi": target.pickup_date.isoformat(),
        "donus_tarihi": target.dropoff_date.isoformat(),
    }
