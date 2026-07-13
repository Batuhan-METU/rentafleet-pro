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
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.floor_pricing.models import (
    RentalIncome,
    VehicleExpense,
    VehicleFinancialProfile,
)

from backend.common.permissions import IsFleetManager
from backend.apps.floor_pricing.serializers import (
    RentalIncomeSerializer,
    VehicleExpenseSerializer,
    VehicleFinancialProfileSerializer,
    expense_category_choices,
)
from backend.infrastructure.services.common.date_helper import resolve_rental_window
from backend.infrastructure.services.pricing.rental_economics_service import (
    build_pricing_decision_payload,
    rental_days_between,
)
from backend.common.multitenancy_tools.scope import (
    get_scoped_expense,
    get_scoped_income,
    get_scoped_vehicle,
)


class VehicleFinancialProfileView(APIView):
    """GET/PUT /api/vehicles/<pk>/financial-profile/ — profil oku/yaz."""

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
    """GET/POST /api/vehicles/<pk>/expenses/ — gider listele/ekle."""

    serializer_class = VehicleExpenseSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[VehicleExpense]:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        return VehicleExpense.objects.filter(vehicle=vehicle)

    def perform_create(self, serializer: VehicleExpenseSerializer) -> None:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        serializer.save(vehicle=vehicle)


class ExpenseDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/expenses/<pk>/ — tek gider yönetimi."""

    serializer_class = VehicleExpenseSerializer
    permission_classes = (IsFleetManager,)

    def get_object(self):
        return get_scoped_expense(self.request, self.kwargs["pk"])


class VehicleIncomeListCreateView(ListCreateAPIView):
    """GET/POST /api/vehicles/<pk>/incomes/ — kiralama geliri listele/ekle."""

    serializer_class = RentalIncomeSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[RentalIncome]:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        return RentalIncome.objects.filter(vehicle=vehicle)

    def perform_create(self, serializer: RentalIncomeSerializer) -> None:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        serializer.save(vehicle=vehicle)


class IncomeDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/incomes/<pk>/ — tek gelir yönetimi."""

    serializer_class = RentalIncomeSerializer
    permission_classes = (IsFleetManager,)

    def get_object(self):
        return get_scoped_income(self.request, self.kwargs["pk"])


class VehiclePricingDecisionView(APIView):
    """GET /api/vehicles/<pk>/pricing-decision/ — şeffaf maliyet tabanı karar desteği.

    Mevcut rental_economics hesaplarını waterfall formatında döner.
    Piyasa verisi taban fiyatı etkilemez; yalnızca karşılaştırma sunar.

    Query:
      * ``baslangic_tarihi`` / ``bitis_tarihi`` — kiralama gün sayısı
      * ``teklif`` veya ``fiyat`` — müdürün toplam teklifi (kâr önizlemesi)
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
        offered_raw = request.query_params.get("teklif") or request.query_params.get("fiyat")
        offered = float(offered_raw) if offered_raw not in (None, "") else None

        payload = build_pricing_decision_payload(
            vehicle,
            days,
            pickup_date=window.pickup_date,
            dropoff_date=window.dropoff_date,
            offered_total_price=offered,
        )
        payload["arama"] = {
            "alis_tarihi": window.pickup_date.isoformat(),
            "donus_tarihi": window.dropoff_date.isoformat(),
            "kiralanan_gun": days,
        }
        return Response(payload)


class ExpenseCategoryListView(APIView):
    """GET /api/expense-categories/ — form için gider kategorileri."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        return Response({"kategoriler": expense_category_choices()})