"""Araç listesi ve araç bazlı operasyon görünümleri."""
from __future__ import annotations

from django.db.models import Exists, OuterRef, QuerySet
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.infrastructure.clickhouse.client import suppress_http_warnings
from backend.apps.floor_pricing.models import VehicleFinancialProfile
from backend.apps.vehicles.models import (
    Vehicle,
    VehicleStatus,
)
from backend.common.permissions import IsFleetManager, IsFleetStaff
from backend.apps.vehicles.serializers import VehicleSerializer, VehicleWriteSerializer
from backend.infrastructure.services.analytics.anomaly_service import detect_fleet_critical_vehicle_ids, detect_vehicle_anomalies
from backend.infrastructure.services.common.logging_utils import quiet_loggers
from backend.infrastructure.services.analytics.maintenance_service import get_maintenance_alerts
from backend.infrastructure.services.analytics.scoring_service import driver_comment, score_for_vehicle_driver
from backend.infrastructure.services.sipp.sipp_service import format_marka_model_sinif, resolve_sipp
from backend.common.multitenancy_tools.scope import company_vehicle_ids, get_scoped_vehicle, require_user_company, scoped_vehicles


class VehicleListView(ListCreateAPIView):
    """GET/POST /api/vehicles/ — fleet listesi ve yeni araç oluşturma.

    GET (Filo Personeli): sayfalı liste, kullanıcının şirketiyle otomatik kapsanır.
    Filtreler: ``?status=<AVAILABLE|RENTED|MAINTENANCE>``.

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
        queryset = (
            scoped_vehicles(self.request)
            .select_related("company")
            .annotate(
                has_financial_profile_annotated=Exists(
                    VehicleFinancialProfile.objects.filter(vehicle=OuterRef("pk"))
                )
            )
            .order_by("plate_number")
        )

        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status.upper())

        return queryset

    def perform_create(self, serializer: VehicleWriteSerializer) -> None:
        company = require_user_company(self.request)
        serializer.save(company=company)


class VehicleDetailUpdateView(RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/vehicles/<pk>/ — araç detayı + finansal güncelleme.

    GET: künye, TCO alanları ve ``maliyet_analizi`` (günlük maliyet kartı) döner.
    Oluşturma ``VehicleListView`` (POST /vehicles/) üzerinden yapılır.
    """

    serializer_class = VehicleWriteSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[Vehicle]:
        return scoped_vehicles(self.request).select_related("company")


class VehicleCurrentRenterScoreView(APIView):
    """GET /api/vehicles/<pk>/current-renter-score/ — aracın güncel kiracısının skoru.

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


class VehicleAnomalyView(APIView):
    """GET /api/vehicles/<pk>/anomalies/ — güvenlik anomalileri.

    ``anomaly_service`` ile aracın telemetrisini analiz eder (ClickHouse
    erişilemezse deterministik fallback) ve Türkçe yapılandırılmış JSON döner.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        company = require_user_company(request)
        allowed_ids = frozenset(company_vehicle_ids(company.pk))
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
    """GET /api/vehicles/live-stream/ — tüm araçların en güncel konumu.

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
        company = require_user_company(request)
        allowed_ids: frozenset[int] = frozenset(company_vehicle_ids(company.pk))

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
    """GET /api/vehicles/maintenance-alerts/ — öngörücü bakım uyarıları.

    İlgilenilmesi gereken araçları (kalan km'ye göre acil sırayla) Türkçe
    yapılandırılmış JSON olarak döndürür.
    """

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)
        alerts = get_maintenance_alerts(company_id=company.pk)
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