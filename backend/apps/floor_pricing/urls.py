from django.urls import path

from backend.apps.floor_pricing.views import (
    ExpenseCategoryListView,
    ExpenseDetailView,
    IncomeDetailView,
    VehicleExpenseListCreateView,
    VehicleFinancialProfileView,
    VehicleIncomeListCreateView,
    VehiclePricingDecisionView,
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
    path("vehicles/<int:pk>/expenses/", VehicleExpenseListCreateView.as_view(), name="vehicle-expenses"),
    path("vehicles/<int:pk>/incomes/", VehicleIncomeListCreateView.as_view(), name="vehicle-incomes"),
    path("expenses/<int:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
    path("incomes/<int:pk>/", IncomeDetailView.as_view(), name="income-detail"),
    path("expense-categories/", ExpenseCategoryListView.as_view(), name="expense-categories"),
]