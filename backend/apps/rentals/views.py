"""Kiralama API görünümleri."""

from __future__ import annotations

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.application.rental.cancel_rental import cancel_rental
from backend.application.rental.create_rental import RentalCreateInput, create_rental
from backend.application.rental.return_processing import (
    extend_active_rental,
    process_vehicle_return,
)
from backend.apps.rentals.models import (
    Rental,
    RentalStatus,
)
from backend.apps.rentals.serializers import (
    RentalCreateSerializer,
    RentalExtendSerializer,
    RentalReturnSerializer,
    RentalSerializer,
)
from backend.common.audit import log_change
from backend.common.excel_response import xlsx_attachment_response
from backend.common.idempotency import idempotent
from backend.common.multitenancy_tools.scope import (
    get_scoped_driver,
    get_scoped_rental,
    get_scoped_vehicle,
    require_user_company,
)
from backend.common.permissions import IsFleetStaff
from backend.infrastructure.services.reporting.rental_export_service import (
    build_rental_workbook,
)


def _rental_queryset(company_id: int):
    # "-id" eşitlik bozucu — started_at tek başına benzersiz değil, bkz.
    # Rental.Meta.ordering docstring'i. Sayfalanan (Geçmiş) listede
    # deterministik sıra olmadan aynı kayıt iki sayfada birden çıkabilir.
    return (
        Rental.objects.filter(company_id=company_id)
        .select_related("driver", "vehicle")
        .order_by("-started_at", "-id")
    )


def _period_filter_q(period: str, *, now) -> Q | None:
    """``rental_period_code`` sınıflandırmasının DB seviyesindeki karşılığı.

    ``ACTIVE`` başlamış (``started_at <= now``) ve henüz kapatılmamış TÜM
    kiralamaları kapsar — sözleşme bitiş tarihi geçmiş ama araç henüz teslim
    alınmamış olanlar da burada kalır (ayrı bir "gecikmiş" kategorisi yok,
    bkz. ``rental_is_overdue`` — bu sadece Aktif kümesi içinde bir uyarı
    bayrağıdır).
    """
    period = period.upper()
    if period == "CANCELLED":
        return Q(status=RentalStatus.CANCELLED)
    if period == "PAST":
        return Q(status=RentalStatus.COMPLETED)
    if period == "UPCOMING":
        return Q(status=RentalStatus.ACTIVE, started_at__gt=now)
    if period == "ACTIVE":
        return Q(status=RentalStatus.ACTIVE, started_at__lte=now)
    return None


def _summary_counts(company_id: int, *, now) -> dict:
    """Sekme rozetlerindeki sayılar — sayfalanan/kesilen veriden değil, her
    zaman tam tablodan (indexli, ucuz ``.count()`` sorguları).

    ``active_overdue``: Aktif kümesinin İÇİNDE, sözleşme bitiş tarihi geçmiş
    ama henüz teslim alınmamış kiralama sayısı — Aktif sekmesinde kırmızı
    uyarı rozeti için (ayrı bir sekme/kategori değil).

    ``past_*`` alt-kırılımları, Geçmiş sekmesindeki Tümü/Zamanında/Erken/Geç
    filtre butonlarının sayılarını sayfalama sonrasında da doğru göstermek
    için — bunlar artık geçerli sayfadaki veriden değil buradan gelir.
    """
    base = _rental_queryset(company_id)
    active_qs = base.filter(_period_filter_q("ACTIVE", now=now))
    past_qs = base.filter(_period_filter_q("PAST", now=now))
    return {
        "active": active_qs.count(),
        "active_overdue": active_qs.filter(ended_at__lt=now).count(),
        "upcoming": base.filter(_period_filter_q("UPCOMING", now=now)).count(),
        "past": past_qs.count(),
        "past_on_time": past_qs.filter(return_status="ON_TIME").count(),
        "past_early": past_qs.filter(return_status="EARLY").count(),
        "past_late": past_qs.filter(return_status="LATE").count(),
    }


class RentalHistoryPagination(PageNumberPagination):
    """Geçmiş kiralamalar için sayfa başı 20 kayıt (genel PAGE_SIZE=25'ten farklı)."""

    page_size = 20


class RentalExportView(APIView):
    """GET /api/rentals/export/ — kiralama listesini .xlsx olarak indirir.

    Kiralamalar ekranındaki sekme/alt-filtreyi aynen destekler:
    ``?period=<ACTIVE|UPCOMING|PAST|CANCELLED>`` ve geçmiş sekmesi için
    ``?return_timing=<ON_TIME|EARLY|LATE>``. Filtre gönderilmezse tüm kayıtlar
    dışa aktarılır. Dosya adı: ``Kiralama_Raporu_<YYYY-AA-GG>.xlsx``.
    """

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> HttpResponse:
        company = require_user_company(request)

        qs = _rental_queryset(company.pk)

        period = (request.query_params.get("period") or "").strip()
        if period:
            period_q = _period_filter_q(period, now=timezone.now())
            if period_q is not None:
                qs = qs.filter(period_q)

        return_timing = (request.query_params.get("return_timing") or "").strip().upper()
        if return_timing:
            qs = qs.filter(return_status=return_timing)

        content = build_rental_workbook(qs)
        return xlsx_attachment_response(content, "Kiralama_Raporu")


class RentalListCreateView(APIView):
    """GET /api/rentals/ — liste | POST — yeni kiralama."""

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)

        status_filter = request.query_params.get("status")
        period_filter = (request.query_params.get("period") or "").strip()
        vehicle_filter = request.query_params.get("vehicle_id")
        return_timing = (request.query_params.get("return_timing") or "").strip().upper()
        now = timezone.now()
        qs = _rental_queryset(company.pk)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if period_filter:
            period_q = _period_filter_q(period_filter, now=now)
            if period_q is not None:
                qs = qs.filter(period_q)
        if vehicle_filter:
            qs = qs.filter(vehicle_id=vehicle_filter)

        # Sekme rozetleri her zaman tam tablodan hesaplanır — hangi period/
        # sayfa istenirse istensin, sayılar kesilmiş/sayfalanmış veriden
        # değil gerçek toplamdan gelir.
        summary = _summary_counts(company.pk, now=now)

        if period_filter.upper() == "PAST":
            # Geçmiş kiralamalar birikince tek seferde çekilmez — 20'şer
            # kayıtlık gerçek sayfalama; kullanıcı hangi sayfaya basarsa
            # sadece onun verisi gelir.
            if return_timing:
                qs = qs.filter(return_status=return_timing)
            paginator = RentalHistoryPagination()
            page = paginator.paginate_queryset(qs, request, view=self)
            serialized = RentalSerializer(page, many=True).data
            response = paginator.get_paginated_response(serialized)
            response.data["summary"] = summary
            return response

        rentals = list(qs[:500])
        serialized = RentalSerializer(rentals, many=True).data
        return Response(
            {
                "total": len(serialized),
                "rentals": serialized,
                "summary": summary,
            }
        )

    @idempotent(endpoint="rentals.create")
    def post(self, request: Request) -> Response:
        company = require_user_company(request)

        serializer = RentalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        driver = get_scoped_driver(request, data["driver_id"])
        vehicle = get_scoped_vehicle(request, data["vehicle_id"])

        rental = create_rental(
            company=company,
            data=RentalCreateInput(
                driver=driver,
                vehicle=vehicle,
                pickup_date=data["pickup_date"],
                dropoff_date=data["dropoff_date"],
                pickup_time=data["pickup_time"],
                dropoff_time=data["dropoff_time"],
                daily_rate=data.get("daily_rate"),
                deposit_amount=data.get("deposit_amount"),
            ),
            created_by=request.user,
        )
        return Response(RentalSerializer(rental).data, status=status.HTTP_201_CREATED)


class RentalCancelView(APIView):
    """POST /api/rentals/<pk>/cancel/ — gelecek kiralamayı iptal et veya aktif
    kiralamayı erken teslim olarak kapat.

    Araç henüz teslim alınmadıysa (kiralama Gelecek): fiyat farkı olmadan
    doğrudan iptal edilir, araç hemen boşa düşer. Kiralama zaten
    başlamışsa (Aktif): iptal etmek fiilen "erken teslim" anlamına gelir —
    fark hesaplanıp tahsil/iade edilir, kayıt CANCELLED değil COMPLETED olur.
    """

    permission_classes = (IsFleetStaff,)

    def post(self, request: Request, pk: int) -> Response:
        rental = get_scoped_rental(request, pk)
        result = cancel_rental(rental, cancelled_by=request.user)

        if not result.early_return:
            return Response(RentalSerializer(result.rental).data)

        settlement = result.settlement
        assert settlement is not None  # early_return=True her zaman settlement doldurur
        return Response(
            {
                "status": settlement.return_status,
                "unused_days": settlement.unused_days,
                "overage_hours": settlement.overage_hours,
                "daily_rate": str(settlement.daily_rate),
                "price_difference": str(settlement.price_difference),
                "message": settlement.message,
                "rental": RentalSerializer(result.rental).data,
            }
        )


class RentalReturnView(APIView):
    """POST /api/rentals/<pk>/return/ — araç teslim al (erken/geç/zamanında).

    ``preview: true`` gönderilirse hiçbir kayıt değişmez; yalnızca fark
    hesaplanıp önizleme olarak döner (modal'daki canlı gösterge için).
    """

    permission_classes = (IsFleetStaff,)

    def post(self, request: Request, pk: int) -> Response:
        rental = get_scoped_rental(request, pk)
        if rental.status != RentalStatus.ACTIVE:
            return Response(
                {"error": "Yalnızca aktif kiralamalar teslim alınabilir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RentalReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        is_preview = data.get("preview", False)
        settlement = process_vehicle_return(
            rental,
            data["actual_return_at"],
            data.get("notes", ""),
            preview=is_preview,
        )
        if not is_preview:
            log_change(
                user=request.user,
                obj=rental,
                message=f"Araç teslim alındı: {settlement.message}",
            )

        payload = {
            "preview": data.get("preview", False),
            "status": settlement.return_status,
            "unused_days": settlement.unused_days,
            "overage_hours": settlement.overage_hours,
            "daily_rate": str(settlement.daily_rate),
            "price_difference": str(settlement.price_difference),
            "message": settlement.message,
        }
        if not data.get("preview", False):
            rental.refresh_from_db()
            payload["rental"] = RentalSerializer(rental).data

        return Response(payload)


class RentalExtendView(APIView):
    """POST /api/rentals/<pk>/extend/ — aktif kiralamanın dönüş tarihini ileri ötele.

    Aracın yeni tarih aralığında başka bir aktif kiralaması varsa 400 döner.
    """

    permission_classes = (IsFleetStaff,)

    def post(self, request: Request, pk: int) -> Response:
        rental = get_scoped_rental(request, pk)
        serializer = RentalExtendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        extend_active_rental(rental, serializer.validated_data["new_ended_at"])
        return Response(RentalSerializer(rental).data)