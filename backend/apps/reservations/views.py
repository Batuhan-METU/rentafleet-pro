"""Kiralama / rezervasyon API görünümleri."""

from __future__ import annotations

from datetime import datetime, time

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.common.multitenancy_tools.scope import (
    get_scoped_driver,
    get_scoped_rental,
    get_scoped_vehicle,
    require_user_company,
)
from backend.application.customer.profiles import apply_customer_profiles
from backend.application.customer.snapshots import ensure_customer_profiles
from backend.application.customer.rental_stats import sync_rental_history_stats
from backend.application.rental.evaluate_application import RentalApplicationService
from backend.application.rental.reservation_guard import enforce_risk_and_eligibility
from backend.application.rental.return_processing import extend_active_rental, process_vehicle_return
from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import (
    RentalApplication,
)
from backend.apps.reservations.models import (
    Rental,
    RentalStatus,
)
from backend.apps.vehicles.models import VehicleStatus

from backend.common.permissions import IsFleetManager, IsFleetStaff
from backend.apps.risk_checks.serializers import (
    RentalApplicationCreateSerializer,
    RentalApplicationSerializer,
    RentalDecisionLogSerializer,
)
from backend.apps.reservations.serializers import (
    RentalCreateSerializer,
    RentalExtendSerializer,
    RentalReturnSerializer,
    RentalSerializer,
)


def _rental_queryset(company_id: int):
    return (
        Rental.objects.filter(driver__company_id=company_id)
        .select_related("driver", "vehicle")
        .order_by("-started_at")
    )


def _datetime_at(d, *, hour: int = 10, minute: int = 0) -> datetime:
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(d, time(hour=hour, minute=minute)), tz)


def _donem_filter_q(donem: str, *, now) -> Q | None:
    """``rental_donem_kodu`` sınıflandırmasının DB seviyesindeki karşılığı."""
    donem = donem.upper()
    if donem == "IPTAL":
        return Q(status=RentalStatus.CANCELLED)
    if donem == "GECMIS":
        return Q(status=RentalStatus.COMPLETED)
    if donem == "GELECEK":
        return Q(status=RentalStatus.ACTIVE, started_at__gt=now)
    if donem == "AKTIF":
        return Q(status=RentalStatus.ACTIVE, started_at__lte=now)
    return None


class RentalListCreateView(APIView):
    """GET /api/rentals/ — liste | POST — yeni rezervasyon."""

    permission_classes = (IsFleetStaff,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)

        status_filter = request.query_params.get("status")
        donem_filter = request.query_params.get("donem")
        now = timezone.now()
        qs = _rental_queryset(company.pk)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if donem_filter:
            donem_q = _donem_filter_q(donem_filter, now=now)
            if donem_q is not None:
                qs = qs.filter(donem_q)

        rentals = list(qs[:500])
        serialized = RentalSerializer(rentals, many=True).data
        return Response(
            {
                "toplam": len(serialized),
                "kiralamalar": serialized,
                "ozet": {
                    "aktif": sum(1 for r in serialized if r["donem_kodu"] == "AKTIF"),
                    "gelecek": sum(1 for r in serialized if r["donem_kodu"] == "GELECEK"),
                    "gecmis": sum(1 for r in serialized if r["donem_kodu"] == "GECMIS"),
                },
            }
        )

    def post(self, request: Request) -> Response:
        company = require_user_company(request)

        serializer = RentalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        driver = get_scoped_driver(request, data["driver_id"])
        vehicle = get_scoped_vehicle(request, data["vehicle_id"])

        # Kara liste dahil tüm risk engelleri aşağıdaki risk kapısında
        # (BLACKLIST kuralı) değerlendirilir; burada erken kontrol yapılmaz ki
        # engellenen deneme RentalDecisionLog'a düşsün.
        started_at = _datetime_at(data["pickup_date"])
        ended_at = _datetime_at(data["dropoff_date"])
        now = timezone.now()
        is_future = started_at > now

        daily_rate = data.get("daily_rate")
        total_days = max((data["dropoff_date"] - data["pickup_date"]).days, 1)
        quoted_total = daily_rate * total_days if daily_rate is not None else None

        if driver.rentals.filter(
            status=RentalStatus.ACTIVE,
            started_at__lt=ended_at,
            ended_at__gt=started_at,
        ).exists():
            return Response(
                {"error": "Sürücünün bu tarihlerde çakışan bir rezervasyonu var."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if vehicle.rentals.filter(
            status=RentalStatus.ACTIVE,
            started_at__lt=ended_at,
            ended_at__gt=started_at,
        ).exists():
            return Response(
                {"error": "Aracın bu tarihlerde çakışan bir rezervasyonu var."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not is_future and vehicle.status != VehicleStatus.AVAILABLE:
            return Response(
                {"error": "Seçilen araç müsait değil."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Risk + araç uygunluk kapısı: taze bir risk değerlendirmesi çalıştırır,
        # RentalDecisionLog'a yazar ve seçilen aracın sürücünün risk seviyesine
        # uygun segmentte olduğunu doğrular. Başarısızsa ValidationError fırlatır
        # (DRF dispatch bunu otomatik olarak 400 yanıtına çevirir).
        #
        # Bilerek DIŞARIDA çalıştırılır: enforce_risk_and_eligibility kendi
        # atomic bloklarını kullanır (RentalApplicationService), böylece
        # reddedilen bir denemenin RentalDecisionLog kaydı, aşağıdaki
        # rezervasyon oluşturma bloğu hiç çalışmasa bile kalıcı olur. Eğer bu
        # çağrı tüm post() tek bir @transaction.atomic içinde olsaydı,
        # fırlatılan ValidationError audit kayıtlarını da geri alırdı.
        application = enforce_risk_and_eligibility(
            company=company,
            driver=driver,
            vehicle=vehicle,
            created_by=request.user,
            requested_pickup_at=started_at,
            requested_return_at=ended_at,
        )

        with transaction.atomic():
            rental = Rental.objects.create(
                driver=driver,
                vehicle=vehicle,
                status=RentalStatus.ACTIVE,
                started_at=started_at,
                ended_at=ended_at,
                original_ended_at=ended_at,
                start_km=vehicle.current_km,
                quoted_total=quoted_total,
                daily_rate=daily_rate,
                deposit_amount=data.get("deposit_amount"),
                application=application,
            )

            if not is_future:
                vehicle.status = VehicleStatus.RENTED
                vehicle.save(update_fields=["status"])

            sync_rental_history_stats(driver)

        return Response(RentalSerializer(rental).data, status=status.HTTP_201_CREATED)


class RentalCancelView(APIView):
    """POST /api/rentals/<pk>/cancel/ — gelecek rezervasyonu iptal et veya aktif
    rezervasyonu erken teslim olarak kapat.

    Araç henüz teslim alınmadıysa (rezervasyon Gelecek): fiyat farkı olmadan
    doğrudan iptal edilir, araç hemen boşa düşer. Rezervasyon zaten
    başlamışsa (Aktif): iptal etmek fiilen "erken teslim" anlamına gelir —
    fark hesaplanıp tahsil/iade edilir, kayıt CANCELLED değil COMPLETED olur.
    """

    permission_classes = (IsFleetStaff,)

    def post(self, request: Request, pk: int) -> Response:
        rental = get_scoped_rental(request, pk)
        if rental.status != RentalStatus.ACTIVE:
            return Response(
                {"error": "Yalnızca aktif rezervasyonlar iptal edilebilir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        if rental.started_at > now:
            with transaction.atomic():
                rental.status = RentalStatus.CANCELLED
                rental.save(update_fields=["status"])
                sync_rental_history_stats(rental.driver)
            return Response(RentalSerializer(rental).data)

        settlement = process_vehicle_return(rental, now)
        rental.refresh_from_db()
        return Response(
            {
                "durum": settlement.return_status,
                "kullanilmayan_gun": settlement.unused_days,
                "rotar_saat": settlement.overage_hours,
                "gunluk_ucret": str(settlement.daily_rate),
                "fark_tutari": str(settlement.price_difference),
                "mesaj": settlement.message,
                "kiralama": RentalSerializer(rental).data,
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
                {"error": "Yalnızca aktif rezervasyonlar teslim alınabilir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RentalReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        settlement = process_vehicle_return(
            rental,
            data["actual_return_at"],
            data.get("notes", ""),
            preview=data.get("preview", False),
        )

        payload = {
            "onizleme": data.get("preview", False),
            "durum": settlement.return_status,
            "kullanilmayan_gun": settlement.unused_days,
            "rotar_saat": settlement.overage_hours,
            "gunluk_ucret": str(settlement.daily_rate),
            "fark_tutari": str(settlement.price_difference),
            "mesaj": settlement.message,
        }
        if not data.get("preview", False):
            rental.refresh_from_db()
            payload["kiralama"] = RentalSerializer(rental).data

        return Response(payload)


class RentalExtendView(APIView):
    """POST /api/rentals/<pk>/extend/ — aktif kiralamanın dönüş tarihini ileri ötele.

    Aracın yeni tarih aralığında başka bir aktif rezervasyonu varsa 400 döner.
    """

    permission_classes = (IsFleetStaff,)

    def post(self, request: Request, pk: int) -> Response:
        rental = get_scoped_rental(request, pk)
        serializer = RentalExtendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        extend_active_rental(rental, serializer.validated_data["new_ended_at"])
        return Response(RentalSerializer(rental).data)


class RentalApplicationListCreateView(APIView):
    permission_classes = (IsAuthenticated, IsFleetManager)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)
        apps = (
            RentalApplication.objects.filter(company_id=company.pk)
            .select_related("driver")
            .order_by("-created_at")[:50]
        )
        return Response(RentalApplicationSerializer(apps, many=True).data)

    def post(self, request: Request) -> Response:
        user = request.user
        company = require_user_company(request)
        serializer = RentalApplicationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = RentalApplicationService()

        if data.get("driver_id"):
            driver = get_object_or_404(Driver, pk=data["driver_id"], company_id=company.pk)
        else:
            driver_data = data.get("driver")
            if not driver_data:
                return Response(
                    {"error": "driver_id veya driver bilgisi gerekli."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                driver = Driver.objects.create(company_id=company.pk, **driver_data)
            except IntegrityError:
                return Response(
                    {"error": "Bu TC kimlik numarası bu şirkette zaten kayıtlı."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ensure_customer_profiles(driver)
        apply_customer_profiles(driver, data)

        application = service.create_application(
            company=company,
            driver=driver,
            created_by=user,
            requested_pickup_at=data.get("requested_pickup_at"),
            requested_return_at=data.get("requested_return_at"),
        )
        return Response(
            RentalApplicationSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


class RentalApplicationDetailView(APIView):
    permission_classes = (IsAuthenticated, IsFleetManager)

    def get(self, request: Request, pk: int) -> Response:
        company = require_user_company(request)
        application = get_object_or_404(
            RentalApplication,
            pk=pk,
            company_id=company.pk,
        )
        return Response(RentalApplicationSerializer(application).data)


class RentalApplicationEvaluateView(APIView):
    permission_classes = (IsAuthenticated, IsFleetManager)

    def post(self, request: Request, pk: int) -> Response:
        company = require_user_company(request)
        application = get_object_or_404(
            RentalApplication,
            pk=pk,
            company_id=company.pk,
        )
        service = RentalApplicationService()
        result = service.evaluate(application)
        application.refresh_from_db()
        payload = service.serialize_evaluation(result, application)
        return Response(payload)


class RentalApplicationDecisionLogView(APIView):
    permission_classes = (IsAuthenticated, IsFleetManager)

    def get(self, request: Request, pk: int) -> Response:
        company = require_user_company(request)
        application = get_object_or_404(
            RentalApplication,
            pk=pk,
            company_id=company.pk,
        )
        logs = application.decision_logs.order_by("created_at")
        return Response(RentalDecisionLogSerializer(logs, many=True).data)