"""Enuygun piyasa fiyatları — CompetitorPrice üretimi (API'den bağımsız okuma katmanı)."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from backend.apps.enuygun.models import CompetitorPrice
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.common.date_helper import RentalDateWindow, rental_window
from backend.infrastructure.services.enuygun.reservation_filter import (
    MarketSegmentReport,
    ReservationFilter,
)

logger = logging.getLogger(__name__)


def _persist_reports(
    vehicle: Vehicle,
    reports: list[MarketSegmentReport],
    *,
    window: RentalDateWindow,
) -> int:
    saved = 0

    with transaction.atomic():
        # Aracın bu pencereye ait TÜM eski satırları (her iki match_basis)
        # tek seferde silinir; ardından her rapor kendi satırlarını yazar.
        CompetitorPrice.objects.filter(
            vehicle=vehicle,
            pickup_date=window.pickup_date,
            dropoff_date=window.dropoff_date,
        ).delete()

        for report in reports:
            # seen_refs HER rapor için ayrı — aynı ilan hem SIPP hem TSB
            # tip kodu yöntemiyle eşleşebilir, biri diğerini "duplicate"
            # sayıp elemesin diye.
            seen_refs: set[str] = set()
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
                    # Bilgi amaçlı denormalize alan; eşleştirme SIPP/TSB tip
                    # koduyla yapıldı (bkz. ReservationFilter).
                    sipp_code=(row.segment or "")[:4],
                    match_basis=report.match_basis,
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
    # Tek filtre örneği tüm filo için kullanılır: ilan TSB değerlemeleri/tip
    # kodları VehicleMatchingService önbelleğinde kalır, araç başına
    # tekrarlanmaz.
    reservation_filter = ReservationFilter()
    vehicle_count = 0
    row_count = 0
    per_vehicle: dict[str, dict] = {}
    sync_errors: list[str] = []

    vehicle_qs = Vehicle.objects.filter(company_id=company_id).order_by("plate_number")
    for vehicle in vehicle_qs:
        try:
            sipp_report = reservation_filter.build_sipp_report(reservations, vehicle)
            tsb_report = reservation_filter.build_tsb_type_code_report(reservations, vehicle)
            row_count += _persist_reports(vehicle, [sipp_report, tsb_report], window=window)
            vehicle_count += 1
            per_vehicle[str(vehicle.pk)] = {
                "sipp": sipp_report.to_dict(),
                "tsb_type_code": tsb_report.to_dict(),
            }
        except Exception as exc:
            msg = f"{vehicle.plate_number} senkron hatası: {exc}"
            logger.exception(msg)
            sync_errors.append(msg)

    return {
        "vehicle_count": vehicle_count,
        "row_count": row_count,
        "vehicles": per_vehicle,
        "errors": sync_errors,
    }


def sync_fleet_market_prices(
    *,
    force: bool = True,
    window: RentalDateWindow | None = None,
    company_id: int,
) -> dict:
    from backend.infrastructure.services.enuygun.market_cache_service import (
        fetch_enuygun_market_snapshot,
        rebuild_competitor_prices_for_window,
    )

    target = window or rental_window()
    cache_status = fetch_enuygun_market_snapshot(window=target, force=force)
    rebuild = rebuild_competitor_prices_for_window(target, company_id=company_id)

    return {
        "vehicle_count": rebuild["vehicle_count"],
        "row_count": rebuild["row_count"],
        "total_reservations": cache_status.reservation_count,
        "fetched_reservations": cache_status.reservation_count,
        "cache": cache_status.to_dict(),
        "errors": list(cache_status.errors) + list(rebuild.get("errors", [])),
        "vehicles": rebuild["vehicles"],
        "pickup_date": target.pickup_date.isoformat(),
        "dropoff_date": target.dropoff_date.isoformat(),
    }
