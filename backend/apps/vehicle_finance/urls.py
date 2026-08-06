from django.urls import path

from backend.apps.vehicle_finance.views import (
    CompanyOverheadExpenseDetailView,
    CompanyOverheadExpenseListCreateView,
    ExpenseCategoryListView,
    ExpenseDetailView,
    IncomeDetailView,
    InsurancePolicyDetailView,
    LoanAllocationDetailView,
    LoanAllocationListCreateView,
    LoanDetailView,
    LoanListCreateView,
    VehicleExpenseListCreateView,
    VehicleFinancialProfileView,
    VehicleIncomeListCreateView,
    VehicleInsurancePolicyListCreateView,
    VehicleLoanAllocationListView,
    VehiclePricingDecisionView,
    VehicleYearlySummaryView,
)

urlpatterns = [
    path(
        "vehicles/<int:pk>/pricing-decision/",
        VehiclePricingDecisionView.as_view(),
        name="vehicle-pricing-decision",
    ),
    path(
        "vehicles/<int:pk>/financial-profile/",
        VehicleFinancialProfileView.as_view(),
        name="vehicle-financial-profile",
    ),
    path("vehicles/<int:pk>/loans/", VehicleLoanAllocationListView.as_view(), name="vehicle-loans"),
    path(
        "vehicles/<int:pk>/yearly-summary/",
        VehicleYearlySummaryView.as_view(),
        name="vehicle-yearly-summary",
    ),
    path("vehicles/<int:pk>/expenses/", VehicleExpenseListCreateView.as_view(), name="vehicle-expenses"),
    path("vehicles/<int:pk>/incomes/", VehicleIncomeListCreateView.as_view(), name="vehicle-incomes"),
    path("expenses/<int:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
    path("incomes/<int:pk>/", IncomeDetailView.as_view(), name="income-detail"),
    path("expense-categories/", ExpenseCategoryListView.as_view(), name="expense-categories"),
    # --- Gerçek maliyet hesabı (MALIYET_HESAPLAMA_METODOLOJISI §3) ---------
    path("loans/", LoanListCreateView.as_view(), name="loan-list"),
    path("loans/<int:pk>/", LoanDetailView.as_view(), name="loan-detail"),
    path(
        "loans/<int:pk>/allocations/",
        LoanAllocationListCreateView.as_view(),
        name="loan-allocation-list",
    ),
    path(
        "loan-allocations/<int:pk>/",
        LoanAllocationDetailView.as_view(),
        name="loan-allocation-detail",
    ),
    path(
        "vehicles/<int:pk>/insurance-policies/",
        VehicleInsurancePolicyListCreateView.as_view(),
        name="vehicle-insurance-policies",
    ),
    path(
        "insurance-policies/<int:pk>/",
        InsurancePolicyDetailView.as_view(),
        name="insurance-policy-detail",
    ),
    path(
        "overhead-expenses/",
        CompanyOverheadExpenseListCreateView.as_view(),
        name="overhead-expense-list",
    ),
    path(
        "overhead-expenses/<int:pk>/",
        CompanyOverheadExpenseDetailView.as_view(),
        name="overhead-expense-detail",
    ),
]
