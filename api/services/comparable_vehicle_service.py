"""Enuygun API üzerinden filo piyasa fiyat senkronu.

Tek kaynak: Enuygun CR Search API. Tüm segment uyumlu rezervasyonlar
listelenir; en ucuz arama mantığı yoktur.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from api.models import CompetitorPrice, Vehicle
from api.services.date_helper import RentalDateWindow, rental_window
from api.services.enuygun_service import (
    LOCATION_LABEL,
    EnuygunSearchResult,
    EnuygunService,
)
from api.services.reservation_filter import MarketSegmentReport, ReservationFilter

logger = logging.getLogger(__name__)


def _persist_report(vehicle: Vehicle, report: MarketSegmentReport) -> int:
    """Araç için segment raporunu atomik olarak yazar."""
    seen_refs: set[str] = set()
    saved = 0

    with transaction.atomic():
        CompetitorPrice.objects.filter(vehicle=vehicle).delete()

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
            )
            saved += 1

    return saved


def search_market_for_vehicle(
    vehicle: Vehicle,
    *,
    reservations: list[dict] | None = None,
    search_result: EnuygunSearchResult | None = None,
) -> MarketSegmentReport:
    """Tek araç için segment raporu üretir (DB'ye yazmaz)."""
    if reservations is None:
        if search_result is None:
            search_result = EnuygunService().fetch_all_reservations()
        reservations = search_result.reservations
    return ReservationFilter().build_report(reservations, vehicle)


def sync_fleet_market_prices() -> dict:
    """Tüm filo için tek Enuygun araması yapar; her araca segment uyumlu fiyatları yazar."""
    window: RentalDateWindow = rental_window()
    service = EnuygunService()
    search_result = service.fetch_all_reservations(date_window=window)
    reservation_filter = ReservationFilter()

    vehicle_count = 0
    row_count = 0
    per_vehicle: dict[str, dict] = {}
    sync_errors: list[str] = list(search_result.errors)

    for vehicle in Vehicle.objects.all().order_by("plate_number"):
        try:
            report = reservation_filter.build_report(search_result.reservations, vehicle)
            row_count += _persist_report(vehicle, report)
            vehicle_count += 1
            per_vehicle[str(vehicle.pk)] = report.to_dict()
        except Exception as exc:
            msg = f"{vehicle.plate_number} senkron hatası: {exc}"
            logger.exception(msg)
            sync_errors.append(msg)

    return {
        "arac_sayisi": vehicle_count,
        "kayit_sayisi": row_count,
        "toplam_rezervasyon": search_result.total_count,
        "cekilen_rezervasyon": len(search_result.reservations),
        "sayfa_sayisi": search_result.pages_fetched,
        "sehir": LOCATION_LABEL,
        "alis_tarihi": window.pickup_date_iso,
        "donus_tarihi": window.dropoff_date_iso,
        "hatalar": sync_errors,
        "araclar": per_vehicle,
    }
