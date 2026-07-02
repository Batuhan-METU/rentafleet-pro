"""Relational read-only API views (RentA-Fleet PRO, v1).

Day 13: tüm iş uçları kimlik doğrulama ve RBAC ile korunur.
  * IsFleetStaff      — araç listesi, canlı takip, bakım, sürücü skoru.
  * IsFleetManager    — analitik, AI, fiyatlandırma, anomali, yakıt optimizasyonu.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from django.db.models import Count, Prefetch, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsFleetManager, IsFleetStaff

from api.clickhouse_client import suppress_http_warnings
from api.models import Company, CompetitorPrice, Vehicle, VehicleStatus
from api.serializers import CompanySerializer, CompetitorPriceSerializer, VehicleSerializer
from api.services.ai_consultant_service import get_ai_fleet_advice
from api.services.analytics_service import get_fleet_analytics
from api.services.anomaly_service import detect_vehicle_anomalies
from api.services.fuel_service import get_fuel_optimization_data
from api.services.maintenance_service import get_maintenance_alerts
from api.services.market_pricing_service import build_market_pricing_advice
from api.services.comparable_vehicle_service import sync_fleet_market_prices
from api.services.date_helper import rental_window
from api.services.enuygun_service import LOCATION_LABEL
from api.services.statistics_calculator import calculate_statistics, statistics_to_dict
from api.services.scoring_service import driver_comment, score_for_vehicle_driver
from api.services.sipp_service import format_marka_model_sinif, resolve_sipp


@contextmanager
def _quiet_anomaly_logs() -> Iterator[None]:
    """Silence the anomaly service's per-vehicle fallback WARNINGs while
    scanning the whole fleet (otherwise one live-stream request logs a line
    per vehicle). Levels are always restored.
    """
    lg = logging.getLogger("api.services.anomaly_service")
    previous = lg.level
    lg.setLevel(logging.ERROR)
    try:
        yield
    finally:
        lg.setLevel(previous)


class CompanyListView(ListAPIView):
    """GET /api/v1/companies/ — kurulumdaki şirket kaydı (müdür)."""

    serializer_class = CompanySerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[Company]:
        # Annotate fleet size in SQL to avoid an N+1 in the serializer.
        return Company.objects.annotate(vehicle_count=Count("vehicles")).order_by("name")


class VehicleListView(ListAPIView):
    """GET /api/v1/vehicles/ — paginated list of fleet vehicles.

    Supports optional filtering via query params:
      * ``?company=<id>``
      * ``?status=<AVAILABLE|RENTED|MAINTENANCE>``
    """

    serializer_class = VehicleSerializer
    permission_classes = (IsFleetStaff,)

    def get_queryset(self) -> QuerySet[Vehicle]:
        # select_related collapses the company join into one query.
        queryset = Vehicle.objects.select_related("company").order_by("plate_number")

        company_id = self.request.query_params.get("company")
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status.upper())

        return queryset


class VehicleCurrentRenterScoreView(APIView):
    """GET /api/v1/vehicles/<pk>/current-renter-score/ — aracın güncel kiracısının skoru.

    Skor araca değil, o anda aracı kullanan (veya son kullanan) sürücüye aittir.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_object_or_404(Vehicle, pk=pk)
        result = score_for_vehicle_driver(vehicle.pk)
        if result is None:
            return Response(
                {
                    "vehicle_id": vehicle.pk,
                    "kiraci_var_mi": False,
                    "mesaj": "Bu araca bağlı aktif veya geçmiş kiralama kaydı bulunamadı.",
                }
            )
        return Response(
            {
                "vehicle_id": vehicle.pk,
                "kiraci_var_mi": True,
                "driver_id": result.driver_id,
                "driver_score": result.score,
                "summary": {
                    "toplam_hiz_ihlali": result.total_violations,
                    "toplam_ani_fren": result.total_brakes,
                    "toplam_ani_hizlanma": result.total_accelerations,
                    "kiralama_sayisi": result.rental_count,
                    "surus_yorumu": driver_comment(result.score),
                },
            }
        )


class VehicleFuelOptimizationView(APIView):
    """GET /api/v1/vehicles/<pk>/fuel-optimization/ — yakıt & rota optimizasyonu.

    ``fuel_service`` üzerinden ideal hız, tahmini tasarruf ve Türkçe AI
    tavsiyesini hesaplar (ClickHouse erişilemezse deterministik tahmine düşer).
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_object_or_404(Vehicle, pk=pk)
        data = get_fuel_optimization_data(vehicle.pk)
        return Response(
            {
                "vehicle_id": data.vehicle_id,
                "ideal_hiz_limiti": data.ideal_speed,
                "tahmini_tasarruf_yuzdesi": data.estimated_savings_pct,
                "ai_tavsiyesi": data.advice,
                "rota_optimizasyonu": {
                    "en_uygun_bölge": data.route_recommendation,
                },
            }
        )


class VehicleAnomalyView(APIView):
    """GET /api/v1/vehicles/<pk>/anomalies/ — güvenlik anomalileri.

    ``anomaly_service`` ile aracın telemetrisini analiz eder (ClickHouse
    erişilemezse deterministik fallback) ve Türkçe yapılandırılmış JSON döner.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_object_or_404(Vehicle, pk=pk)
        anomalies = detect_vehicle_anomalies(vehicle.pk)
        return Response(
            {
                "vehicle_id": vehicle.pk,
                "anomali_var_mi": len(anomalies) > 0,
                "anomaliler": [
                    {
                        "tip": anomaly.type,
                        "seviye": anomaly.level,
                        "mesaj": anomaly.message,
                        "tarih": anomaly.timestamp,
                    }
                    for anomaly in anomalies
                ],
            }
        )


class VehiclePricingView(APIView):
    """GET /api/v1/vehicles/<pk>/suggested-price/ — akıllı fiyat önerisi.

    Rakip ``CompetitorPrice`` kayıtları varsa piyasa ortalamasına göre
    ``ai_tavsiyesi`` ve ayrıntılı ``gerekce`` üretir; yoksa yield motoru
  sonucunu döndürür.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        get_object_or_404(Vehicle, pk=pk)
        advice = build_market_pricing_advice(pk)
        return Response(
            {
                "vehicle_id": advice.vehicle_id,
                "taban_fiyat": advice.taban_fiyat,
                "onerilen_fiyat": advice.onerilen_fiyat,
                "gerekce": advice.gerekce,
                "ai_tavsiyesi": advice.ai_tavsiyesi,
                "piyasa_ortalamasi": advice.piyasa_ortalamasi,
                "rakip_sayisi": advice.rakip_sayisi,
                "rakipler": [
                    {"kaynak": q.kaynak, "gunluk_fiyat": q.gunluk_fiyat}
                    for q in advice.rakipler
                ],
                "yield_fiyat": advice.yield_fiyat,
                "yield_gerekce": advice.yield_gerekce,
            }
        )


def _competitor_price_payload(
    vehicle: Vehicle,
    rows: list[CompetitorPrice],
    *,
    pickup,
    dropoff,
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
    """GET /api/v1/vehicles/<pk>/competitor-prices/ — otomatik piyasa fiyatları.

    Veriler ``fleet/market-prices/sync/`` ile toplu çekilir; bu uç yalnızca okur.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_object_or_404(Vehicle, pk=pk)
        rows = list(
            CompetitorPrice.objects.filter(vehicle=vehicle).order_by("source_name")
        )
        window = rental_window()
        return Response(
            _competitor_price_payload(
                vehicle,
                rows,
                pickup=window.pickup_date,
                dropoff=window.dropoff_date,
            )
        )


class FleetCompetitorPricesView(APIView):
    """GET /api/v1/fleet/competitor-prices/ — tüm filonun piyasa fiyatları (tek istek)."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        window = rental_window()
        price_qs = CompetitorPrice.objects.order_by("source_name")
        vehicles = Vehicle.objects.prefetch_related(
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
            )

        return Response(
            {
                "arac_sayisi": len(araclar),
                "arama": {
                    "sehir": LOCATION_LABEL,
                    "alis_tarihi": window.pickup_date_iso,
                    "donus_tarihi": window.dropoff_date_iso,
                },
                "araclar": araclar,
            }
        )


class FleetMarketSyncView(APIView):
    """POST /api/v1/fleet/market-prices/sync/ — tüm filo için Enuygun piyasa taraması.

    Enuygun API üzerinden Ankara fiyatlarını çeker; segment uyumlu tüm firmaları yazar.
    """

    permission_classes = (IsFleetManager,)

    def post(self, request: Request) -> Response:
        result = sync_fleet_market_prices()
        return Response(
            {
                "mesaj": "Filo piyasa fiyatları Enuygun üzerinden güncellendi.",
                **result,
            }
        )


# Backend-side Turkish labels for the live-stream payload (frontend has its
# own map; this keeps the API response self-describing and human-readable).
_STATUS_TR = {
    VehicleStatus.AVAILABLE: "Müsait",
    VehicleStatus.RENTED: "Kirada",
    VehicleStatus.MAINTENANCE: "Bakımda",
}


class VehicleLiveStreamView(APIView):
    """GET /api/v1/vehicles/live-stream/ — tüm araçların en güncel konumu.

    Her aracın *en son* canlı durumunu (konum, hız, yakıt, olay, durum)
    döndürür. Veri, simülatörün güncellediği dayanıklı ``VehicleLiveState``
    anlık görüntüsünden okunur; bu sayede ClickHouse kapalı olsa bile canlı
    takip kesintisiz çalışır. Henüz pingi olmayan araçlar varsayılan
    (Ankara merkez, hız 0) değerlerle listelenir.
    """

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> Response:
        vehicles = list(
            Vehicle.objects.select_related("live_state").order_by("plate_number")
        )

        # Day 6 güvenlik analizi: kritik anomalisi olan araçları haritada
        # vurgulamak için bir kez (tüm filo) hesaplanır. ClickHouse kapalıysa
        # deterministik fallback devreye girer; loglar susturulur.
        critical_ids: set[int] = set()
        with suppress_http_warnings(), _quiet_anomaly_logs():
            for vehicle in vehicles:
                anomalies = detect_vehicle_anomalies(vehicle.pk)
                if any(a.level == "KRITIK" for a in anomalies):
                    critical_ids.add(vehicle.pk)

        live_vehicles = []
        for vehicle in vehicles:
            state = getattr(vehicle, "live_state", None)
            live_vehicles.append(
                {
                    "id": vehicle.pk,
                    "plaka": vehicle.plate_number,
                    "marka_model": f"{vehicle.brand} {vehicle.model}",
                    "marka_model_sinif": format_marka_model_sinif(
                        vehicle.brand, vehicle.model, vehicle.sipp_code
                    ),
                    "sipp_code": resolve_sipp(
                        vehicle.brand, vehicle.model, vehicle.sipp_code
                    ).code,
                    "durum": _STATUS_TR.get(vehicle.status, vehicle.status),
                    "durum_kodu": vehicle.status,
                    "enlem": round(state.latitude, 6) if state else None,
                    "boylam": round(state.longitude, 6) if state else None,
                    "hiz": round(state.speed, 1) if state else 0.0,
                    "yakit_seviyesi": round(state.fuel_level, 1) if state else None,
                    "olay": state.event_type if state else "normal",
                    "kritik_anomali": vehicle.pk in critical_ids,
                    "son_guncelleme": (
                        state.updated_at.isoformat() if state else None
                    ),
                }
            )

        return Response(
            {
                "arac_sayisi": len(live_vehicles),
                "araclar": live_vehicles,
            }
        )


class VehicleMaintenanceAlertView(APIView):
    """GET /api/v1/vehicles/maintenance-alerts/ — öngörücü bakım uyarıları.

    İlgilenilmesi gereken araçları (kalan km'ye göre acil sırayla) Türkçe
    yapılandırılmış JSON olarak döndürür.
    """

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> Response:
        alerts = get_maintenance_alerts()
        return Response(
            {
                "uyari_sayisi": len(alerts),
                "araclar": [
                    {
                        "id": alert.vehicle_id,
                        "plaka": alert.plate,
                        "marka_model": alert.brand_model,
                        "guncel_km": alert.current_km,
                        "hedef_km": alert.target_km,
                        "kalan_km": alert.remaining_km,
                        "ilerleme_yuzdesi": alert.progress_pct,
                        "durum": alert.status,
                        "agresif_surus": alert.aggressive,
                        "surus_skoru": alert.driver_score,
                    }
                    for alert in alerts
                ],
            }
        )


class FleetAnalyticsView(APIView):
    """GET /api/v1/fleet/analytics/ — dashboard için filo analitiği.

    Toplam/doluluk, aktif kritik anomali, ortalama sürücü skoru, en düşük
    skorlu 5 araç ve haftalık yakıt tasarruf trendini tek yanıtta döndürür.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        data = get_fleet_analytics()
        return Response(
            {
                "toplam_arac": data.total,
                "kirada": data.rented,
                "musait": data.available,
                "bakimda": data.maintenance,
                "doluluk_orani": data.occupancy_rate,
                "aktif_kritik_anomali": data.critical_count,
                "ortalama_surus_skoru": data.avg_score,
                "en_dusuk_skorlu_suruculer": data.lowest_drivers,
                "haftalik_yakit_tasarrufu": data.weekly_fuel_savings,
            }
        )


class AIConsultantView(APIView):
    """POST /api/v1/ai/consult/ — AI Filo Danışmanı.

    Gövde: ``{"query": "Hangi araçlar riskte?"}``. ``ai_consultant_service``
    anlık filo verilerini toplar, OpenAI anahtarı varsa modeli çağırır, aksi
    halde veriye dayalı kurumsal Türkçe fallback yanıtı üretir.
    """

    permission_classes = (IsFleetManager,)

    def post(self, request: Request) -> Response:
        query = request.data.get("query", "")
        if not isinstance(query, str) or not query.strip():
            return Response(
                {"error": "Lütfen bir soru girin ('query' alanı boş olamaz)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answer = get_ai_fleet_advice(query)
        return Response({"response": answer})
