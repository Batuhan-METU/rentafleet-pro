"""Piyasa fiyatı ve rakip fiyat API görünümleri."""
from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.models import CompetitorPrice, Vehicle
from backend.permissions import IsFleetManager
from backend.serializers import CompetitorPriceSerializer
from backend.infrastructure.services.common.date_helper import RentalDateWindow, resolve_rental_window
from backend.infrastructure.services.market.enuygun_service import LOCATION_LABEL
from backend.infrastructure.services.market.market_cache_service import (
    ensure_market_data_for_window,
    read_snapshot_meta,
    rebuild_competitor_prices_for_window,
)
from backend.infrastructure.services.market.statistics_calculator import calculate_statistics, statistics_to_dict
from backend.infrastructure.services.sipp.sipp_service import resolve_sipp
from backend.tenant.scope import get_scoped_vehicle, get_user_company, scoped_vehicles


def _resolve_market_window(request: Request) -> tuple[RentalDateWindow, bool]:
    """Query param'lardan kiralama penceresi; ikinci değer varsayılan mı."""
    return resolve_rental_window(
        baslangic_tarihi=request.query_params.get("baslangic_tarihi"),
        bitis_tarihi=request.query_params.get("bitis_tarihi"),
    )


def _prepare_market_read(
    request: Request,
    *,
    company_id: int | None = None,
) -> tuple[RentalDateWindow, bool, dict]:
    """Varsayılan pencerede salt DB; gelecek tarihte yalnızca önbellek okunur."""
    window, is_default = _resolve_market_window(request)
    if is_default:
        cache_meta = read_snapshot_meta(window)
        cache_meta["varsayilan_pencere"] = True
        rebuild_competitor_prices_for_window(window, company_id=company_id)
    else:
        status_obj = ensure_market_data_for_window(
            window,
            on_demand=True,
            company_id=company_id,
        )
        cache_meta = status_obj.to_dict()
        cache_meta["hedef_baslangic"] = window.pickup_date_iso
        cache_meta["hedef_bitis"] = window.dropoff_date_iso
        cache_meta["varsayilan_pencere"] = False
    return window, is_default, cache_meta


def _arama_block(window: RentalDateWindow, *, varsayilan_pencere: bool) -> dict:
    return {
        "sehir": LOCATION_LABEL,
        "alis_tarihi": window.pickup_date_iso,
        "donus_tarihi": window.dropoff_date_iso,
        "hedef_baslangic": window.pickup_date_iso,
        "hedef_bitis": window.dropoff_date_iso,
        "varsayilan_pencere": varsayilan_pencere,
    }


def _competitor_price_payload(
    vehicle: Vehicle,
    rows: list[CompetitorPrice],
    *,
    pickup,
    dropoff,
    varsayilan_pencere: bool = True,
) -> dict:
    """Tek araç için Enuygun segment piyasa JSON gövdesi."""
    profile = resolve_sipp(vehicle.brand, vehicle.model, vehicle.sipp_code or None)
    sipp = vehicle.sipp_code or profile.code

    matched_vehicles = []
    for row in rows:
        parts = (row.similar_vehicle or "").split(" ", 1)
        brand = parts[0] if parts else vehicle.brand
        model = parts[1] if len(parts) > 1 else (row.similar_vehicle or vehicle.model)
        provider = (row.provider_name or row.source_name or "").strip()
        matched_vehicles.append(
            {
                "provider": provider,
                "brand": brand,
                "model": model,
                "vehicleClass": profile.segment_label,
                "segment": row.sipp_code or sipp,
                "dailyPrice": float(row.daily_price),
            }
        )

    prices = [float(row.daily_price) for row in rows]
    statistics = statistics_to_dict(calculate_statistics(prices))

    arama = {
        "sehir": LOCATION_LABEL,
        "alis_tarihi": pickup.isoformat() if hasattr(pickup, "isoformat") else str(pickup),
        "donus_tarihi": dropoff.isoformat() if hasattr(dropoff, "isoformat") else str(dropoff),
        "hedef_baslangic": pickup.isoformat() if hasattr(pickup, "isoformat") else str(pickup),
        "hedef_bitis": dropoff.isoformat() if hasattr(dropoff, "isoformat") else str(dropoff),
        "varsayilan_pencere": varsayilan_pencere,
    }

    piyasa_teklifleri = [
        {
            "kaynak": item["provider"],
            "benzer_arac": f"{item['brand']} {item['model']}".strip(),
            "gunluk_fiyat": item["dailyPrice"],
        }
        for item in matched_vehicles
    ]

    return {
        "vehicle_id": vehicle.pk,
        "plaka": vehicle.plate_number,
        "marka_model": f"{vehicle.brand} {vehicle.model}",
        "km": vehicle.current_km,
        "sipp_code": sipp,
        "sinif_etiketi": profile.segment_label,
        "matchedSegment": sipp,
        "vehicleCount": len(matched_vehicles),
        "matchedVehicles": matched_vehicles,
        "statistics": statistics,
        "arama": arama,
        "piyasa_teklifleri": piyasa_teklifleri,
        "rakipler": CompetitorPriceSerializer(rows, many=True).data,
    }


class VehicleCompetitorPriceView(APIView):
    """GET /api/v1/vehicles/<pk>/competitor-prices/ — piyasa fiyatları (tarih filtrelenebilir)."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        company = get_user_company(request)
        company_id = company.pk if company else None
        try:
            window, is_default, cache_meta = _prepare_market_read(
                request,
                company_id=company_id,
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
                    varsayilan_pencere=is_default,
                ),
                "onbellek": cache_meta,
            }
        )


class FleetCompetitorPricesView(APIView):
    """GET /api/v1/fleet/competitor-prices/ — filo piyasa fiyatları (tarih filtrelenebilir)."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        company = get_user_company(request)
        company_id = company.pk if company else None
        try:
            window, is_default, cache_meta = _prepare_market_read(
                request,
                company_id=company_id,
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

        araclar: dict[str, dict] = {}
        for vehicle in vehicles:
            rows = list(vehicle.competitor_prices.all())
            araclar[str(vehicle.pk)] = _competitor_price_payload(
                vehicle,
                rows,
                pickup=window.pickup_date,
                dropoff=window.dropoff_date,
                varsayilan_pencere=is_default,
            )

        return Response(
            {
                "arac_sayisi": len(araclar),
                "arama": _arama_block(window, varsayilan_pencere=is_default),
                "onbellek": cache_meta,
                "araclar": araclar,
            }
        )
