"""Araç listesi ve araç bazlı operasyon görünümleri."""
from __future__ import annotations

from django.db.models import Exists, OuterRef, Prefetch, QuerySet
from django.http import HttpResponse
from rest_framework.generics import DestroyAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.vehicle_finance.models import RentalIncome, VehicleFinancialProfile
from backend.apps.vehicles.models import (
    Vehicle,
    VehicleDocument,
    VehicleStatus,
)
from backend.apps.vehicles.serializers import (
    VehicleDocumentSerializer,
    VehicleSerializer,
    VehicleWriteSerializer,
)
from backend.common.excel_response import xlsx_attachment_response
from backend.common.multitenancy_tools.scope import (
    company_vehicle_ids,
    get_scoped_document,
    get_scoped_vehicle,
    require_user_company,
    scoped_vehicles,
)
from backend.common.permissions import IsFleetManager, IsFleetStaff
from backend.infrastructure.clickhouse.client import suppress_http_warnings
from backend.infrastructure.services.analytics.anomaly_service import (
    detect_fleet_critical_vehicle_ids,
)
from backend.infrastructure.services.analytics.maintenance_service import (
    STATUS_CRITICAL,
    STATUS_HEALTHY,
    STATUS_WARNING,
    get_maintenance_statuses,
)
from backend.infrastructure.services.common.logging_utils import quiet_loggers
from backend.infrastructure.services.reporting.fleet_export_service import (
    build_fleet_inventory_workbook,
)
from backend.infrastructure.services.reporting.maintenance_export_service import (
    build_maintenance_workbook,
)
from backend.infrastructure.services.sipp.sipp_service import (
    format_brand_model_segment,
    resolve_sipp,
)


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
            .select_related("company", "financial_profile")
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


class VehicleDocumentListCreateView(ListCreateAPIView):
    """GET/POST /api/vehicles/<pk>/documents/ — "Dosyalar ve Ekler" listele/yükle."""

    serializer_class = VehicleDocumentSerializer
    permission_classes = (IsFleetManager,)
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self) -> QuerySet[VehicleDocument]:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        return VehicleDocument.objects.filter(vehicle=vehicle)

    def perform_create(self, serializer: VehicleDocumentSerializer) -> None:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        uploaded_file = serializer.validated_data["file"]
        serializer.save(
            vehicle=vehicle,
            original_filename=uploaded_file.name,
            content_type=uploaded_file.content_type or "",
            size=uploaded_file.size,
            uploaded_by=self.request.user,
        )


class VehicleDocumentDetailView(DestroyAPIView):
    """DELETE /api/vehicle-documents/<pk>/ — dosyayı sil."""

    serializer_class = VehicleDocumentSerializer
    permission_classes = (IsFleetManager,)

    def get_object(self) -> VehicleDocument:
        return get_scoped_document(self.request, self.kwargs["pk"])


_STATUS_TR = {
    VehicleStatus.AVAILABLE: "Müsait",
    VehicleStatus.RENTED: "Kirada",
    VehicleStatus.MAINTENANCE: "Bakımda",
}


def _tr_lower(text: str) -> str:
    """Türkçe uyumlu küçük harfe çevirme (İ→i, I→ı)."""
    return text.replace("İ", "i").replace("I", "ı").lower()


class VehicleExportView(APIView):
    """GET /api/vehicles/export/ — filo envanterini .xlsx olarak indirir.

    Fleet Management ekranındaki listeyle aynı filtreleri destekler:
    ``?status=<AVAILABLE|RENTED|MAINTENANCE>`` ve ``?q=<plaka/marka/model>``.
    Filtre gönderilmezse tüm filo dışa aktarılır. Dosya adı dinamiktir:
    ``Filo_Envanter_Raporu_<YYYY-AA-GG>.xlsx``.
    """

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> HttpResponse:
        # `_vehicle_row` (fleet_export_service) her araç için maliyet/kâr
        # hesabı çalıştırır — `financial_profile` (OneToOne) select_related
        # ile, `incomes` (RentalIncome) prefetch_related ile önceden
        # yüklenir; aksi halde N araçlık bir filo dışa aktarımı N adet ekstra
        # sorgu tetiklerdi (bkz. performans denetimi bulgusu).
        queryset = (
            scoped_vehicles(request)
            .select_related("financial_profile")
            .prefetch_related(
                Prefetch(
                    "incomes",
                    queryset=RentalIncome.objects.order_by("-start_date"),
                    to_attr="prefetched_incomes",
                ),
            )
            .order_by("plate_number")
        )

        status = (request.query_params.get("status") or "").strip().upper()
        if status and status != "ALL":
            queryset = queryset.filter(status=status)

        vehicles = list(queryset)

        # Arama, UI'daki davranışı birebir yansıtır: plaka + marka + model
        # birleşiminde Türkçe uyumlu, harf duyarsız "içerir" kontrolü.
        query = (request.query_params.get("q") or "").strip()
        if query:
            needle = _tr_lower(query)
            vehicles = [
                vehicle
                for vehicle in vehicles
                if needle
                in _tr_lower(f"{vehicle.plate_number} {vehicle.brand} {vehicle.model}")
            ]

        content = build_fleet_inventory_workbook(vehicles)
        return xlsx_attachment_response(content, "Filo_Envanter_Raporu")


class VehicleMaintenanceExportView(APIView):
    """GET /api/vehicles/maintenance-alerts/export/ — bakım raporu (.xlsx).

    Bakım Merkezi ekranındaki üç DIŞLAYICI kümeyi aynen destekler:
    ``?status_filter=PENDING`` (varsayılan; yalnızca yaklaşan/WARNING),
    ``?status_filter=URGENT`` (yalnızca acil/CRITICAL) ve
    ``?status_filter=HEALTHY`` (sağlıklı araçlar).
    Dosya adı: ``Bakim_Raporu_<YYYY-AA-GG>.xlsx``.
    """

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> HttpResponse:
        company = require_user_company(request)
        statuses = get_maintenance_statuses(company_id=company.pk)

        status_filter = (request.query_params.get("status_filter") or "PENDING").strip().upper()
        if status_filter == "URGENT":
            rows = [s for s in statuses if s.status == STATUS_CRITICAL]
        elif status_filter == "HEALTHY":
            rows = [s for s in statuses if s.status == STATUS_HEALTHY]
        else:  # PENDING (varsayılan) = yalnızca yaklaşan (WARNING) — acil DAHİL DEĞİL
            rows = [s for s in statuses if s.status == STATUS_WARNING]

        content = build_maintenance_workbook(rows)
        return xlsx_attachment_response(content, "Bakim_Raporu")


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
                    "plate_number": vehicle.plate_number,
                    "brand_model": f"{vehicle.brand} {vehicle.model}",
                    "brand_model_segment": format_brand_model_segment(
                        vehicle.brand, vehicle.model, vehicle.sipp_code
                    ),
                    "sipp_code": resolve_sipp(
                        vehicle.brand, vehicle.model, vehicle.sipp_code
                    ).code,
                    "status_label": _STATUS_TR.get(vehicle.status, vehicle.status),
                    "status_code": vehicle.status,
                    "latitude": round(state.latitude, 6) if state else None,
                    "longitude": round(state.longitude, 6) if state else None,
                    "speed": round(state.speed, 1) if state else 0.0,
                    "fuel_level": round(state.fuel_level, 1) if state else None,
                    "event": state.event_type if state else "normal",
                    "critical_anomaly": vehicle.pk in critical_ids,
                    "last_updated": (
                        state.updated_at.isoformat() if state else None
                    ),
                }
            )

        return Response(
            {
                "vehicle_count": len(live_vehicles),
                "vehicles": live_vehicles,
            }
        )


class VehicleMaintenanceAlertView(APIView):
    """GET /api/vehicles/maintenance-alerts/ — öngörücü bakım durumları.

    Şirketin TÜM araçlarını (sağlıklı dahil), en acilden en sağlıklıya
    sıralı Türkçe yapılandırılmış JSON olarak döndürür — km VE tarih
    boyutu birlikte (bkz. maintenance_service.py).
    """

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)
        statuses = get_maintenance_statuses(company_id=company.pk)
        healthy_count = sum(1 for s in statuses if s.status == STATUS_HEALTHY)
        critical_count = sum(1 for s in statuses if s.status == STATUS_CRITICAL)
        warning_count = len(statuses) - healthy_count - critical_count
        return Response(
            {
                "healthy_count": healthy_count,
                "warning_count": warning_count,
                "critical_count": critical_count,
                "alert_count": warning_count + critical_count,
                "vehicles": [
                    {
                        "id": s.vehicle_id,
                        "plate_number": s.plate,
                        "brand_model": s.brand_model,
                        "current_km": s.current_km,
                        "status": s.status,
                        "km_status": s.km_status,
                        "date_status": s.date_status,
                        "last_maintenance_date": s.last_maintenance_date.isoformat()
                        if s.last_maintenance_date
                        else None,
                        "last_maintenance_km": s.last_maintenance_km,
                        "target_km": s.target_km,
                        "remaining_km": s.remaining_km,
                        "progress_pct": s.progress_pct,
                        "target_date": s.target_date.isoformat() if s.target_date else None,
                        "remaining_days": s.remaining_days,
                    }
                    for s in statuses
                ],
            }
        )