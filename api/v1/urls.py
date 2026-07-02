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
  * GET /api/v1/vehicles/<pk>/suggested-price/      — dynamic pricing
  * GET /api/v1/vehicles/<pk>/competitor-prices/     — read Enuygun segment prices
  * GET /api/v1/fleet/competitor-prices/             — all fleet competitor prices (bulk)
  * POST /api/v1/fleet/market-prices/sync/           — sync all fleet prices via Enuygun API
  * GET /api/v1/vehicles/live-stream/               — latest live position of all vehicles
  * GET /api/v1/vehicles/maintenance-alerts/        — predictive maintenance alerts
  * GET /api/v1/fleet/analytics/                    — aggregated dashboard analytics
  * POST /api/v1/ai/consult/                        — AI fleet consultant chatbot
  * POST /api/v1/auth/login/                       — token login
  * GET  /api/v1/auth/me/                          — current user profile
  * POST /api/v1/auth/logout/                      — revoke token
"""

from django.urls import path

from api.auth_views import LoginView, LogoutView, MeView
from api.driver_views import (
    DriverDetailView,
    DriverListView,
    DriverRentalHistoryView,
    DriverScoreView,
)
from api.v1.views import HealthCheckView
from api.views import (
    AIConsultantView,
    CompanyListView,
    FleetAnalyticsView,
    FleetCompetitorPricesView,
    FleetMarketSyncView,
    VehicleAnomalyView,
    VehicleCompetitorPriceView,
    VehicleCurrentRenterScoreView,
    VehicleFuelOptimizationView,
    VehicleListView,
    VehicleLiveStreamView,
    VehicleMaintenanceAlertView,
    VehiclePricingView,
)

app_name = "v1"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("companies/", CompanyListView.as_view(), name="company-list"),
    path("drivers/", DriverListView.as_view(), name="driver-list"),
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
        "vehicles/<int:pk>/suggested-price/",
        VehiclePricingView.as_view(),
        name="vehicle-suggested-price",
    ),
    path(
        "vehicles/<int:pk>/competitor-prices/",
        VehicleCompetitorPriceView.as_view(),
        name="vehicle-competitor-prices",
    ),
    path("fleet/analytics/", FleetAnalyticsView.as_view(), name="fleet-analytics"),
    path(
        "fleet/competitor-prices/",
        FleetCompetitorPricesView.as_view(),
        name="fleet-competitor-prices",
    ),
    path(
        "fleet/market-prices/sync/",
        FleetMarketSyncView.as_view(),
        name="fleet-market-sync",
    ),
    path("ai/consult/", AIConsultantView.as_view(), name="ai-consult"),
]
