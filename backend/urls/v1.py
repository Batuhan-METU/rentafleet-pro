"""Version 1 of the RentA-Fleet PRO REST API.

Routes:
  * GET /api/v1/health/                          — readiness probe (both data stores)
  * GET /api/v1/companies/                        — list tenant companies
  * GET /api/v1/vehicles/                         — list fleet vehicles (filter by company/status)
  * GET /api/v1/drivers/                              — list fleet drivers
  * GET /api/v1/drivers/<pk>/                         — driver detail
  * GET /api/v1/drivers/<pk>/driver-score/            — driver driving score
  * GET /api/v1/drivers/<pk>/rentals/                 — driver rental history
  * GET /api/v1/vehicles/<pk>/current-renter-score/   — current renter score for vehicle
  * GET /api/v1/vehicles/<pk>/fuel-optimization/   — fuel & route optimization
  * GET /api/v1/vehicles/<pk>/anomalies/           — security anomaly detection
  * GET /api/v1/vehicles/<pk>/competitor-prices/     — read Enuygun segment prices
  * GET /api/v1/fleet/competitor-prices/             — all fleet competitor prices (bulk, DB read)
  * GET /api/v1/vehicles/live-stream/               — latest live position of all vehicles
  * GET /api/v1/vehicles/maintenance-alerts/        — predictive maintenance alerts
  * GET /api/v1/fleet/analytics/                    — aggregated dashboard analytics
  * POST /api/v1/ai/consult/                        — AI fleet consultant chatbot
  * POST /api/v1/auth/login/                       — token login
  * GET  /api/v1/auth/me/                          — current user profile
  * POST /api/v1/auth/logout/                      — revoke token
"""

from django.urls import path

from backend.views.health import HealthCheckView
from backend.views import (
    AIConsultantView,
    CompanyListView,
    CreateNewTenantView,
    DriverCreateView,
    DriverDetailView,
    DriverListView,
    DriverRentalHistoryView,
    DriverScoreView,
    ExpenseCategoryListView,
    ExpenseDetailView,
    FleetAnalyticsView,
    FleetCompetitorPricesView,
    IncomeDetailView,
    LoginView,
    LogoutView,
    MeView,
    PersonnelManagementView,
    RentalApplicationDecisionLogView,
    RentalApplicationDetailView,
    RentalApplicationEvaluateView,
    RentalApplicationListCreateView,
    RentalCancelView,
    RentalListCreateView,
    TenantBrandingView,
    VehicleAnomalyView,
    VehicleCompetitorPriceView,
    VehicleCreateView,
    VehicleCurrentRenterScoreView,
    VehicleExpenseListCreateView,
    VehicleFinancialAnalysisView,
    VehicleFinancialProfileView,
    VehicleFuelOptimizationView,
    VehicleIncomeListCreateView,
    VehicleListView,
    VehicleLiveStreamView,
    VehicleMaintenanceAlertView,
    VehicleRentalQuoteView,
)

app_name = "v1"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("saas/tenants/", CreateNewTenantView.as_view(), name="saas-create-tenant"),
    path("tenant/branding/", TenantBrandingView.as_view(), name="tenant-branding"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("personnel/", PersonnelManagementView.as_view(), name="personnel"),
    path("companies/", CompanyListView.as_view(), name="company-list"),
    path("drivers/", DriverListView.as_view(), name="driver-list"),
    path("drivers/create/", DriverCreateView.as_view(), name="driver-create"),
    path("drivers/<int:pk>/", DriverDetailView.as_view(), name="driver-detail"),
    path(
        "drivers/<int:pk>/driver-score/",
        DriverScoreView.as_view(),
        name="driver-score",
    ),
    path(
        "drivers/<int:pk>/rentals/",
        DriverRentalHistoryView.as_view(),
        name="driver-rentals",
    ),
    path("rentals/", RentalListCreateView.as_view(), name="rental-list-create"),
    path("rentals/<int:pk>/cancel/", RentalCancelView.as_view(), name="rental-cancel"),
    path("vehicles/", VehicleListView.as_view(), name="vehicle-list"),
    path(
        "vehicles/live-stream/",
        VehicleLiveStreamView.as_view(),
        name="vehicle-live-stream",
    ),
    path(
        "vehicles/maintenance-alerts/",
        VehicleMaintenanceAlertView.as_view(),
        name="vehicle-maintenance-alerts",
    ),
    path(
        "vehicles/<int:pk>/current-renter-score/",
        VehicleCurrentRenterScoreView.as_view(),
        name="vehicle-current-renter-score",
    ),
    path(
        "vehicles/<int:pk>/fuel-optimization/",
        VehicleFuelOptimizationView.as_view(),
        name="vehicle-fuel-optimization",
    ),
    path(
        "vehicles/<int:pk>/anomalies/",
        VehicleAnomalyView.as_view(),
        name="vehicle-anomalies",
    ),
    path(
        "vehicles/<int:pk>/competitor-prices/",
        VehicleCompetitorPriceView.as_view(),
        name="vehicle-competitor-prices",
    ),
    # --- Finansal karar destek modülü ---------------------------------
    path(
        "vehicles/<int:pk>/rental-quote/",
        VehicleRentalQuoteView.as_view(),
        name="vehicle-rental-quote",
    ),
    path(
        "vehicles/<int:pk>/financial-analysis/",
        VehicleFinancialAnalysisView.as_view(),
        name="vehicle-financial-analysis",
    ),
    path(
        "vehicles/<int:pk>/financial-profile/",
        VehicleFinancialProfileView.as_view(),
        name="vehicle-financial-profile",
    ),
    path(
        "vehicles/<int:pk>/expenses/",
        VehicleExpenseListCreateView.as_view(),
        name="vehicle-expenses",
    ),
    path(
        "vehicles/<int:pk>/incomes/",
        VehicleIncomeListCreateView.as_view(),
        name="vehicle-incomes",
    ),
    path("expenses/<int:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
    path("incomes/<int:pk>/", IncomeDetailView.as_view(), name="income-detail"),
    path(
        "expense-categories/",
        ExpenseCategoryListView.as_view(),
        name="expense-categories",
    ),
    # NOT: <int:pk> güncelleme rotası, spesifik alt rotalardan sonra gelir.
    path("vehicles/<int:pk>/", VehicleCreateView.as_view(), name="vehicle-detail-update"),
    path("fleet/analytics/", FleetAnalyticsView.as_view(), name="fleet-analytics"),
    path(
        "fleet/competitor-prices/",
        FleetCompetitorPricesView.as_view(),
        name="fleet-competitor-prices",
    ),
    path("ai/consult/", AIConsultantView.as_view(), name="ai-consult"),
    path(
        "rental-applications/",
        RentalApplicationListCreateView.as_view(),
        name="rental-application-list",
    ),
    path(
        "rental-applications/<int:pk>/",
        RentalApplicationDetailView.as_view(),
        name="rental-application-detail",
    ),
    path(
        "rental-applications/<int:pk>/evaluate/",
        RentalApplicationEvaluateView.as_view(),
        name="rental-application-evaluate",
    ),
    path(
        "rental-applications/<int:pk>/decisions/",
        RentalApplicationDecisionLogView.as_view(),
        name="rental-application-decisions",
    ),
]
