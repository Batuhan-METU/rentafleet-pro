"""Finansal karar destek API uçları (RentA-Fleet PRO).

Araç oluşturma/güncelleme, gider ve gelir yönetimi ile aracın tam finansal
analizini (başabaş, ROI, amortisman, AI önerileri) sunar. Tümü Filo Müdürü
yetkisiyle korunur.
"""

from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.models import (
    RentalIncome,
    VehicleExpense,
    VehicleFinancialProfile,
)
from backend.permissions import IsFleetManager
from backend.serializers import (
    RentalIncomeSerializer,
    VehicleExpenseSerializer,
    VehicleFinancialProfileSerializer,
    VehicleWriteSerializer,
    expense_category_choices,
)
from backend.infrastructure.services.common.date_helper import resolve_rental_window
from backend.infrastructure.services.pricing.rental_economics_service import (
    build_rental_quote,
    competitor_quotes_for_vehicle,
    rental_days_between,
)
from backend.tenant.scope import (
    get_scoped_expense,
    get_scoped_income,
    get_scoped_vehicle,
    get_user_company,
    scoped_vehicles,
)


class VehicleCreateView(RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/v1/vehicles/<pk>/ — araç detayı + finansal güncelleme.

    GET: künye, TCO alanları ve ``maliyet_analizi`` (günlük maliyet kartı) döner.
    Oluşturma ``VehicleListView`` (POST /vehicles/) üzerinden yapılır.
    """

    serializer_class = VehicleWriteSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet:
        return scoped_vehicles(self.request).select_related("company")


class VehicleFinancialProfileView(APIView):
    """GET/PUT /api/v1/vehicles/<pk>/financial-profile/ — profil oku/yaz."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        try:
            profile = vehicle.financial_profile
        except VehicleFinancialProfile.DoesNotExist:
            return Response(
                {"finansal_profil_var": False},
                status=status.HTTP_200_OK,
            )
        return Response(VehicleFinancialProfileSerializer(profile).data)

    def put(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        serializer = VehicleFinancialProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        VehicleFinancialProfile.objects.update_or_create(
            vehicle=vehicle, defaults=serializer.validated_data
        )
        return Response(
            VehicleFinancialProfileSerializer(vehicle.financial_profile).data,
            status=status.HTTP_200_OK,
        )


class VehicleExpenseListCreateView(ListCreateAPIView):
    """GET/POST /api/v1/vehicles/<pk>/expenses/ — gider listele/ekle."""

    serializer_class = VehicleExpenseSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[VehicleExpense]:
        get_scoped_vehicle(self.request, self.kwargs["pk"])
        return VehicleExpense.objects.filter(
            vehicle_id=self.kwargs["pk"],
            vehicle__company=get_user_company(self.request),
        )

    def perform_create(self, serializer: VehicleExpenseSerializer) -> None:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        serializer.save(vehicle=vehicle)


class ExpenseDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/v1/expenses/<pk>/ — tek gider yönetimi."""

    serializer_class = VehicleExpenseSerializer
    permission_classes = (IsFleetManager,)
    queryset = VehicleExpense.objects.select_related("vehicle")

    def get_queryset(self) -> QuerySet[VehicleExpense]:
        company = get_user_company(self.request)
        return VehicleExpense.objects.filter(vehicle__company=company)

    def get_object(self):
        return get_scoped_expense(self.request, self.kwargs["pk"])


class VehicleIncomeListCreateView(ListCreateAPIView):
    """GET/POST /api/v1/vehicles/<pk>/incomes/ — kiralama geliri listele/ekle."""

    serializer_class = RentalIncomeSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[RentalIncome]:
        get_scoped_vehicle(self.request, self.kwargs["pk"])
        return RentalIncome.objects.filter(
            vehicle_id=self.kwargs["pk"],
            vehicle__company=get_user_company(self.request),
        )

    def perform_create(self, serializer: RentalIncomeSerializer) -> None:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        serializer.save(vehicle=vehicle)


class IncomeDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/v1/incomes/<pk>/ — tek gelir yönetimi."""

    serializer_class = RentalIncomeSerializer
    permission_classes = (IsFleetManager,)
    queryset = RentalIncome.objects.select_related("vehicle")

    def get_queryset(self) -> QuerySet[RentalIncome]:
        company = get_user_company(self.request)
        return RentalIncome.objects.filter(vehicle__company=company)

    def get_object(self):
        return get_scoped_income(self.request, self.kwargs["pk"])


class VehicleRentalQuoteView(APIView):
    """GET /api/v1/vehicles/<pk>/rental-quote/ — X günlük kiralama maliyet tabanı + kâr önizlemesi.

    Query:
      * ``baslangic_tarihi`` / ``bitis_tarihi`` (YYYY-MM-DD) — kiralama gün sayısı
      * ``teklif`` veya ``fiyat`` — müdürün toplam kiralama teklifi (kâr hesabı için)
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        try:
            window, _ = resolve_rental_window(
                baslangic_tarihi=request.query_params.get("baslangic_tarihi"),
                bitis_tarihi=request.query_params.get("bitis_tarihi"),
            )
        except ValueError as exc:
            return Response({"mesaj": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        days = rental_days_between(window.pickup_date, window.dropoff_date)
        rakipler = competitor_quotes_for_vehicle(
            vehicle.pk,
            pickup_date=window.pickup_date,
            dropoff_date=window.dropoff_date,
        )
        market_avg = None
        if rakipler:
            market_avg = sum(q.gunluk_fiyat for q in rakipler) / len(rakipler)

        offered_raw = request.query_params.get("teklif") or request.query_params.get("fiyat")
        offered = float(offered_raw) if offered_raw not in (None, "") else None

        quote = build_rental_quote(
            vehicle,
            days,
            market_daily_average=market_avg,
            offered_total_price=offered,
        )
        quote["arama"] = {
            "alis_tarihi": window.pickup_date.isoformat(),
            "donus_tarihi": window.dropoff_date.isoformat(),
            "kiralanan_gun": days,
        }
        return Response(quote)


class VehicleFinancialAnalysisView(APIView):
    """GET /api/v1/vehicles/<pk>/financial-analysis/ — maliyet kartı + dönem fiyat özeti."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        try:
            window, _ = resolve_rental_window(
                baslangic_tarihi=request.query_params.get("baslangic_tarihi"),
                bitis_tarihi=request.query_params.get("bitis_tarihi"),
            )
        except ValueError as exc:
            return Response({"mesaj": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        days = rental_days_between(window.pickup_date, window.dropoff_date)
        rakipler = competitor_quotes_for_vehicle(
            vehicle.pk,
            pickup_date=window.pickup_date,
            dropoff_date=window.dropoff_date,
        )
        market_avg = sum(q.gunluk_fiyat for q in rakipler) / len(rakipler) if rakipler else None
        quote = build_rental_quote(vehicle, days, market_daily_average=market_avg)
        return Response(
            {
                "finansal_profil_var": quote.get("maliyet_karti_var", False),
                "kiralama": quote,
            }
        )


class ExpenseCategoryListView(APIView):
    """GET /api/v1/expense-categories/ — form için gider kategorileri."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        return Response({"kategoriler": expense_category_choices()})
