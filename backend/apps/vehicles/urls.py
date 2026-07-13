from django.urls import path

from backend.apps.vehicles.views import (
    VehicleAnomalyView,
    VehicleCurrentRenterScoreView,
    VehicleDetailUpdateView,
    VehicleListView,
    VehicleLiveStreamView,
    VehicleMaintenanceAlertView,
)

urlpatterns = [
    path("vehicles/", VehicleListView.as_view(), name="vehicle-list"),
    path("vehicles/live-stream/", VehicleLiveStreamView.as_view(), name="vehicle-live-stream"),
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
        "vehicles/<int:pk>/anomalies/",
        VehicleAnomalyView.as_view(),
        name="vehicle-anomalies",
    ),
    path("vehicles/<int:pk>/", VehicleDetailUpdateView.as_view(), name="vehicle-detail-update"),
]