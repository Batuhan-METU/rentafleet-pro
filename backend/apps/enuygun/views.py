"""Piyasa fiyatı ve rakip fiyat API görünümleri."""
from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.enuygun.models import CompetitorPrice
from backend.apps.vehicles.models import Vehicle
from backend.apps.vehicles.serializers import CompetitorPriceSerializer
from backend.common.multitenancy_tools.scope import (
    get_scoped_vehicle,
    require_user_company,
    scoped_vehicles,
)
from backend.common.permissions import IsFleetManager
from backend.infrastructure.services.common.date_helper import (
    RentalDateWindow,
    resolve_rental_window,
)
from backend.infrastructure.services.enuygun.enuygun_service import LOCATION_LABEL
from backend.infrastructure.services.enuygun.market_cache_service import (
    ensure_market_data_for_window,
)
from backend.infrastructure.services.enuygun.reservation_filter import (
    MATCH_BASIS_SIPP,
    MATCH_BASIS_TSB_TYPE,
)
from backend.infrastructure.services.enuygun.statistics_calculator import (
    calculate_statistics,
    statistics_to_dict,
)
from backend.infrastructure.services.enuygun.vehicle_matching_service import (
    VehicleMatchingService,
    tier_for_value,
)
from backend.infrastructure.services.sipp.sipp_service import (
    derive_international_sipp_for_vehicle,
    resolve_sipp,
)


def _resolve_market_window(request: Request) -> tuple[RentalDateWindow, bool]:
    """Query param'lardan kiralama penceresi; ikinci değer varsayılan mı."""
    return resolve_rental_window(
        pickup_date_param=request.query_params.get("baslangic_tarihi"),
        dropoff_date_param=request.query_params.get("bitis_tarihi"),
    )


def _prepare_market_read(
    request: Request,
    *,
    company_id: int,
) -> tuple[RentalDateWindow, bool, dict]:
    """Kiralama penceresi için önbelleği doldurur; eksikse Enuygun'dan çeker."""
    window, is_default = _resolve_market_window(request)
    force = str(request.query_params.get("force", "")).lower() in ("1", "true", "yes")
    status_obj = ensure_market_data_for_window(
        window,
        on_demand=True,
        company_id=company_id,
        force=force,
    )
    cache_meta = status_obj.to_dict()
    cache_meta["hedef_baslangic"] = window.pickup_date_iso
    cache_meta["hedef_bitis"] = window.dropoff_date_iso
    cache_meta["varsayilan_pencere"] = is_default
    return window, is_default, cache_meta


def _search_window_block(window: RentalDateWindow, *, is_default_window: bool) -> dict:
    return {
        "sehir": LOCATION_LABEL,
        "alis_tarihi": window.pickup_date_iso,
        "donus_tarihi": window.dropoff_date_iso,
        "hedef_baslangic": window.pickup_date_iso,
        "hedef_bitis": window.dropoff_date_iso,
        "varsayilan_pencere": is_default_window,
    }


def _match_block(rows: list[CompetitorPrice], *, matched_segment: str) -> dict:
    """SIPP veya TSB Tip Kodu eşleşmesi için tek bir sonuç bloğu."""
    matched_vehicles = []
    for row in rows:
        parts = (row.similar_vehicle or "").split(" ", 1)
        brand = parts[0] if parts else ""
        model = parts[1] if len(parts) > 1 else (row.similar_vehicle or "")
        provider = (row.provider_name or row.source_name or "").strip()
        matched_vehicles.append(
            {
                "provider": provider,
                "brand": brand,
                "model": model,
                "segment": row.sipp_code,
                "dailyPrice": float(row.daily_price),
            }
        )

    prices = [float(row.daily_price) for row in rows]
    return {
        "matchedSegment": matched_segment,
        "vehicleCount": len(matched_vehicles),
        "matchedVehicles": matched_vehicles,
        "statistics": statistics_to_dict(calculate_statistics(prices)),
        "rakipler": CompetitorPriceSerializer(rows, many=True).data,
    }


def _competitor_price_payload(
    vehicle: Vehicle,
    rows: list[CompetitorPrice],
    *,
    pickup,
    dropoff,
    is_default_window: bool = True,
    matching_service: VehicleMatchingService | None = None,
) -> dict:
    """Tek araç için Enuygun piyasa JSON gövdesi.

    İki BAĞIMSIZ eşleşme bloğu döner (``sipp_eslesme``/``tsb_eslesme``) —
    bkz. reservation_filter.py'nin modül docstring'i. ``sipp_code``/
    ``sinif_etiketi`` aracın KENDİ (Ziraat'ten gelen, dokunulmayan) SIPP
    kodunu gösterir; eşleşme bloklarındaki kodlar bundan bağımsız türetilir.
    """
    profile = resolve_sipp(vehicle.brand, vehicle.model, vehicle.sipp_code or None)
    sipp = vehicle.sipp_code or profile.code

    matching = matching_service or VehicleMatchingService()
    fleet_value = matching.valuation_for_fleet_vehicle(vehicle)
    fleet_tier = tier_for_value(fleet_value)

    sipp_rows = [row for row in rows if row.match_basis == MATCH_BASIS_SIPP]
    tsb_rows = [row for row in rows if row.match_basis == MATCH_BASIS_TSB_TYPE]

    fleet_intl_sipp = derive_international_sipp_for_vehicle(vehicle)
    fleet_type_match = matching.type_code_for_fleet_vehicle(vehicle)
    tsb_label = (
        f"{fleet_type_match.brand_name} {fleet_type_match.type_name}".strip()
        if fleet_type_match
        else ""
    )

    search_block = {
        "sehir": LOCATION_LABEL,
        "alis_tarihi": pickup.isoformat() if hasattr(pickup, "isoformat") else str(pickup),
        "donus_tarihi": dropoff.isoformat() if hasattr(dropoff, "isoformat") else str(dropoff),
        "hedef_baslangic": pickup.isoformat() if hasattr(pickup, "isoformat") else str(pickup),
        "hedef_bitis": dropoff.isoformat() if hasattr(dropoff, "isoformat") else str(dropoff),
        "varsayilan_pencere": is_default_window,
    }

    return {
        "vehicle_id": vehicle.pk,
        "plaka": vehicle.plate_number,
        "marka_model": f"{vehicle.brand} {vehicle.model}",
        "km": vehicle.current_km,
        "sipp_code": sipp,
        "sinif_etiketi": profile.segment_label,
        "kasko_degeri": float(fleet_value) if fleet_value is not None else None,
        "kasko_segmenti": fleet_tier.label if fleet_tier else None,
        "arama": search_block,
        "sipp_eslesme": _match_block(sipp_rows, matched_segment=fleet_intl_sipp),
        "tsb_eslesme": _match_block(tsb_rows, matched_segment=tsb_label),
    }


class VehicleCompetitorPriceView(APIView):
    """GET /api/vehicles/<pk>/competitor-prices/ — piyasa fiyatları (tarih filtrelenebilir)."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        company = require_user_company(request)
        try:
            window, is_default, cache_meta = _prepare_market_read(
                request,
                company_id=company.pk,
            )
        except ValueError as exc:
            return Response({"mesaj": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        vehicle = get_scoped_vehicle(request, pk)
        rows = list(
            CompetitorPrice.objects.filter(
                vehicle=vehicle,
                pickup_date=window.pickup_date,
                dropoff_date=window.dropoff_date,
            ).order_by("source_name")
        )
        return Response(
            {
                **_competitor_price_payload(
                    vehicle,
                    rows,
                    pickup=window.pickup_date,
                    dropoff=window.dropoff_date,
                    is_default_window=is_default,
                ),
                "onbellek": cache_meta,
            }
        )


class FleetCompetitorPricesView(APIView):
    """GET /api/fleet/competitor-prices/ — filo piyasa fiyatları (tarih filtrelenebilir)."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)
        try:
            window, is_default, cache_meta = _prepare_market_read(
                request,
                company_id=company.pk,
            )
        except ValueError as exc:
            return Response({"mesaj": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        price_qs = CompetitorPrice.objects.filter(
            pickup_date=window.pickup_date,
            dropoff_date=window.dropoff_date,
            vehicle__company=company,
        ).order_by("source_name")
        vehicles = scoped_vehicles(request).prefetch_related(
            Prefetch("competitor_prices", queryset=price_qs)
        ).order_by("plate_number")

        matching = VehicleMatchingService()
        vehicles_payload: dict[str, dict] = {}
        for vehicle in vehicles:
            rows = list(vehicle.competitor_prices.all())
            vehicles_payload[str(vehicle.pk)] = _competitor_price_payload(
                vehicle,
                rows,
                pickup=window.pickup_date,
                dropoff=window.dropoff_date,
                is_default_window=is_default,
                matching_service=matching,
            )

        return Response(
            {
                "arac_sayisi": len(vehicles_payload),
                "arama": _search_window_block(window, is_default_window=is_default),
                "onbellek": cache_meta,
                "araclar": vehicles_payload,
            }
        )
