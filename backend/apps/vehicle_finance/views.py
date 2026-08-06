"""Finansal karar destek API uçları (RentA-Fleet PRO).

Araç oluşturma/güncelleme, gider ve gelir yönetimi ile aracın tam finansal
analizini (başabaş, ROI, amortisman, AI önerileri) sunar. Tümü Filo Müdürü
yetkisiyle korunur.
"""

from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import status
from rest_framework.generics import (
    DestroyAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.vehicle_finance.models import (
    CompanyOverheadExpense,
    InsurancePolicy,
    Loan,
    LoanVehicleAllocation,
    RentalIncome,
    VehicleExpense,
    VehicleFinancialProfile,
)
from backend.apps.vehicle_finance.serializers import (
    CompanyOverheadExpenseSerializer,
    InsurancePolicySerializer,
    LoanDetailSerializer,
    LoanSerializer,
    LoanVehicleAllocationSerializer,
    RentalIncomeSerializer,
    VehicleExpenseSerializer,
    VehicleFinancialProfileSerializer,
    VehicleLoanAllocationSerializer,
    expense_category_choices,
)
from backend.common.multitenancy_tools.scope import (
    get_scoped_expense,
    get_scoped_income,
    get_scoped_loan,
    get_scoped_loan_allocation,
    get_scoped_overhead,
    get_scoped_policy,
    get_scoped_vehicle,
    get_user_company,
    require_user_company,
)
from backend.common.permissions import IsFleetManager
from backend.infrastructure.services.common.date_helper import resolve_rental_window
from backend.infrastructure.services.cost_calculation.credit_interest_service import (
    generate_amortization_schedule,
)
from backend.infrastructure.services.cost_calculation.rental_economics_service import (
    build_pricing_decision_payload,
    build_vehicle_yearly_summary,
    rental_days_between,
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
                {"has_financial_profile": False},
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
      * ``pickup_date`` / ``dropoff_date`` — kiralama gün sayısı
      * ``offered_price`` — müdürün toplam teklifi (kâr önizlemesi)
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        try:
            window, _ = resolve_rental_window(
                pickup_date_param=request.query_params.get("pickup_date"),
                dropoff_date_param=request.query_params.get("dropoff_date"),
            )
        except ValueError as exc:
            return Response({"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        days = rental_days_between(window.pickup_date, window.dropoff_date)
        offered_raw = request.query_params.get("offered_price")
        offered = float(offered_raw) if offered_raw not in (None, "") else None

        payload = build_pricing_decision_payload(
            vehicle,
            days,
            pickup_date=window.pickup_date,
            dropoff_date=window.dropoff_date,
            offered_total_price=offered,
        )
        payload["search"] = {
            "pickup_date": window.pickup_date.isoformat(),
            "dropoff_date": window.dropoff_date.isoformat(),
            "rental_days": days,
        }
        return Response(payload)


class LoanListCreateView(ListCreateAPIView):
    """GET/POST /api/loans/ — şirketin kredilerini listele/ekle (§3.1)."""

    serializer_class = LoanSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[Loan]:
        company = get_user_company(self.request)
        return Loan.objects.filter(company=company) if company else Loan.objects.none()

    def perform_create(self, serializer: LoanSerializer) -> None:
        company = require_user_company(self.request)
        loan = serializer.save(company=company)
        generate_amortization_schedule(loan)


class LoanDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/loans/<pk>/ — kredi parametreleri güncellenince taksit planı yeniden üretilir.

    GET yanıtı, kredi detay sayfası (Taksit Listesi + Kredi Araç Listesi
    sekmeleri) için ``installments``/``vehicle_allocations``'ı nested olarak
    içerir — liste görünümü (``LoanListCreateView``) bunları içermez.
    """

    serializer_class = LoanDetailSerializer
    permission_classes = (IsFleetManager,)

    def get_object(self) -> Loan:
        return get_scoped_loan(self.request, self.kwargs["pk"])

    def perform_update(self, serializer: LoanSerializer) -> None:
        loan = serializer.save()
        generate_amortization_schedule(loan)


class LoanAllocationListCreateView(ListCreateAPIView):
    """GET/POST /api/loans/<pk>/allocations/ — bir krediye bağlı araç tahsislerini listele/ekle (§3.1 Adım 2)."""

    serializer_class = LoanVehicleAllocationSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[LoanVehicleAllocation]:
        loan = get_scoped_loan(self.request, self.kwargs["pk"])
        return LoanVehicleAllocation.objects.filter(loan=loan).select_related("vehicle")

    def perform_create(self, serializer: LoanVehicleAllocationSerializer) -> None:
        loan = get_scoped_loan(self.request, self.kwargs["pk"])
        serializer.save(loan=loan)


class LoanAllocationDetailView(DestroyAPIView):
    """DELETE /api/loan-allocations/<pk>/ — bir tahsisi kaldırır."""

    serializer_class = LoanVehicleAllocationSerializer
    permission_classes = (IsFleetManager,)

    def get_object(self) -> LoanVehicleAllocation:
        return get_scoped_loan_allocation(self.request, self.kwargs["pk"])


class VehicleInsurancePolicyListCreateView(ListCreateAPIView):
    """GET/POST /api/vehicles/<pk>/insurance-policies/ — poliçe listele/ekle (§3.4)."""

    serializer_class = InsurancePolicySerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[InsurancePolicy]:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        return InsurancePolicy.objects.filter(vehicle=vehicle)

    def perform_create(self, serializer: InsurancePolicySerializer) -> None:
        vehicle = get_scoped_vehicle(self.request, self.kwargs["pk"])
        serializer.save(vehicle=vehicle)


class VehicleLoanAllocationListView(APIView):
    """GET /api/vehicles/<pk>/loans/ — aracın kredi tahsislerini listele (salt okunur).

    Kredi oluşturma/tahsis ekleme akışı "Krediler" ekranında (company-scope'lu
    ``/api/loans/...``) kalır; bu uç, araç detay sayfasının "Finansman"
    sekmesi için mevcut ilişkiyi (``LoanVehicleAllocation.vehicle``) ters
    yönden okur. Bugüne kadar tahakkuk eden maliyet rakamları (kredi/nakit/
    genel gider) ``GET /api/vehicles/<pk>/``'nin ``cost_analysis`` alanından
    (``build_cost_analysis_payload``, §3.6+§4'ün TEK doğru orkestratörü)
    gelir — burada tekrar hesaplanmaz.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        allocations = LoanVehicleAllocation.objects.filter(vehicle=vehicle).select_related("loan")
        return Response(
            {"allocations": VehicleLoanAllocationSerializer(allocations, many=True).data}
        )


class VehicleYearlySummaryView(APIView):
    """GET /api/vehicles/<pk>/yearly-summary/?yil=2025 — Araç Detayı "Gelir &
    Gider Özeti"nin yıla göre kırılımı.

    Ana sayfanın (``company_overview_service``) yıl seçici desenine paralel,
    ama TEK araç için: seçili yılın kira geliri, o yılda tahakkuk eden
    gider (``build_cost_breakdown_for_period``) ve o yılın sonundaki/bugünkü
    hibrit günlük maliyet (``build_hybrid_daily_cost``). "Finansman"
    sekmesindeki ömür-boyu (lifetime) rakamlar buradan ETKİLENMEZ — onlar
    hâlâ ``cost_analysis``/``build_cost_analysis_payload`` üzerinden gelir.
    """

    permission_classes = (IsFleetManager,)

    def get(self, request: Request, pk: int) -> Response:
        vehicle = get_scoped_vehicle(request, pk)
        year_param = request.query_params.get("yil")
        year = int(year_param) if year_param else None
        return Response(build_vehicle_yearly_summary(vehicle, year))


class InsurancePolicyDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/insurance-policies/<pk>/ — tek poliçe yönetimi."""

    serializer_class = InsurancePolicySerializer
    permission_classes = (IsFleetManager,)

    def get_object(self) -> InsurancePolicy:
        return get_scoped_policy(self.request, self.kwargs["pk"])


class CompanyOverheadExpenseListCreateView(ListCreateAPIView):
    """GET/POST /api/overhead-expenses/ — şirket genel gideri listele/ekle (§3.3).

    Toplu import için ``import_overhead_expenses`` yönetim komutu kullanılır;
    bu endpoint tekil manuel giriş/düzeltme içindir.
    """

    serializer_class = CompanyOverheadExpenseSerializer
    permission_classes = (IsFleetManager,)

    def get_queryset(self) -> QuerySet[CompanyOverheadExpense]:
        company = get_user_company(self.request)
        return (
            CompanyOverheadExpense.objects.filter(company=company)
            if company
            else CompanyOverheadExpense.objects.none()
        )

    def perform_create(self, serializer: CompanyOverheadExpenseSerializer) -> None:
        company = require_user_company(self.request)
        serializer.save(company=company)


class CompanyOverheadExpenseDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/overhead-expenses/<pk>/ — tek genel gider kaydı yönetimi."""

    serializer_class = CompanyOverheadExpenseSerializer
    permission_classes = (IsFleetManager,)

    def get_object(self) -> CompanyOverheadExpense:
        return get_scoped_overhead(self.request, self.kwargs["pk"])


class ExpenseCategoryListView(APIView):
    """GET /api/expense-categories/ — form için gider kategorileri."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        return Response({"categories": expense_category_choices()})