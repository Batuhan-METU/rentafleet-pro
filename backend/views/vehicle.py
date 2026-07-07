"""Araç listesi ve araç bazlı operasyon görünümleri."""
from __future__ import annotations

from rest_framework.generics import ListCreateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.infrastructure.clickhouse.client import suppress_http_warnings
from backend.models import Vehicle, VehicleStatus
from backend.permissions import IsFleetManager, IsFleetStaff
from backend.serializers import VehicleSerializer, VehicleWriteSerializer
from backend.infrastructure.services.analytics.anomaly_service import detect_fleet_critical_vehicle_ids, detect_vehicle_anomalies
from backend.infrastructure.services.fuel.fuel_service import get_fuel_optimization_data
from backend.infrastructure.services.common.logging_utils import quiet_loggers
from backend.infrastructure.services.analytics.maintenance_service import get_maintenance_alerts
from backend.infrastructure.services.analytics.scoring_service import driver_comment, score_for_vehicle_driver
from backend.infrastructure.services.sipp.sipp_service import format_marka_model_sinif, resolve_sipp
from backend.tenant.scope import company_vehicle_ids, get_scoped_vehicle, get_user_company, scoped_vehicles


class VehicleListView(ListCreateAPIView):
    """GET/POST /api/v1/vehicles/ — fleet listesi ve yeni araç oluşturma.

    GET (Filo Personeli): sayfalı liste. Filtreler:
      * ``?company=<id>``
      * ``?status=<AVAILABLE|RENTED|MAINTENANCE>``

    POST (Filo Müdürü): araç künyesi + iç içe finansal profil ile kayıt.
    """

    permission_classes = (IsFleetStaff,)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VehicleWriteSerializer
        return VehicleSerializer

    def get_permissions(self):
        # Araç eklemek finansal bir karardır: yalnızca Filo Müdürü.
        if self.request.method == "POST":
            return [IsFleetManager()]
        return [IsFleetStaff()]

    def get_queryset(self) -> QuerySet[Vehicle]:
        queryset = scoped_vehicles(self.request).select_related("company").order_by(
            "plate_number"
        )

        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status.upper())

        return queryset

    def perform_create(self, serializer: VehicleWriteSerializer) -> None:
        company = get_user_company(self.request)
        if company is None:
            company = getattr(self.request, "tenant", None)
        serializer.save(company=company)


class VehicleCurrentRenterScoreView(APIView):
    """GET /api/v1/vehicles/<pk>/current-renter-score/ — aracın güncel kiracısının skoru.

    Skor araca değil, o anda aracı kullanan (veya son kullanan) sürücüye aittir.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
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
        vehicle = get_scoped_vehicle(request, pk)
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
        vehicle = get_scoped_vehicle(request, pk)
        company = get_user_company(request)
        allowed_ids = (
            frozenset(company_vehicle_ids(company.pk)) if company else None
        )
        anomalies = detect_vehicle_anomalies(
            vehicle.pk, allowed_vehicle_ids=allowed_ids
        )
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
            scoped_vehicles(request).select_related("live_state").order_by("plate_number")
        )

        # Day 6 güvenlik analizi: kritik anomalisi olan araçları haritada
        # vurgulamak için bir kez (tüm filo) hesaplanır. ClickHouse kapalıysa
        # deterministik fallback devreye girer; loglar susturulur.
        company = get_user_company(request)
        allowed_ids: frozenset[int] | None = None
        if company is not None:
            allowed_ids = frozenset(company_vehicle_ids(company.pk))

        critical_ids: set[int] = set()
        with suppress_http_warnings(), quiet_loggers("backend.infrastructure.services.analytics.anomaly_service"):
            critical_ids = detect_fleet_critical_vehicle_ids(
                [vehicle.pk for vehicle in vehicles],
                allowed_vehicle_ids=allowed_ids,
            )

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
        company = get_user_company(request)
        company_id = company.pk if company else None
        alerts = get_maintenance_alerts(company_id=company_id)
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
