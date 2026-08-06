from django.urls import path

from backend.apps.vehicles.views import (
    VehicleDetailUpdateView,
    VehicleDocumentDetailView,
    VehicleDocumentListCreateView,
    VehicleExportView,
    VehicleListView,
    VehicleLiveStreamView,
    VehicleMaintenanceAlertView,
    VehicleMaintenanceExportView,
)

urlpatterns = [
    path("vehicles/", VehicleListView.as_view(), name="vehicle-list"),
    path("vehicles/export/", VehicleExportView.as_view(), name="vehicle-export"),
    path("vehicles/live-stream/", VehicleLiveStreamView.as_view(), name="vehicle-live-stream"),
    path(
        "vehicles/maintenance-alerts/",
        VehicleMaintenanceAlertView.as_view(),
        name="vehicle-maintenance-alerts",
    ),
    path(
        "vehicles/maintenance-alerts/export/",
        VehicleMaintenanceExportView.as_view(),
        name="vehicle-maintenance-export",
    ),
    path("vehicles/<int:pk>/", VehicleDetailUpdateView.as_view(), name="vehicle-detail-update"),
    path(
        "vehicles/<int:pk>/documents/",
        VehicleDocumentListCreateView.as_view(),
        name="vehicle-documents",
    ),
    path(
        "vehicle-documents/<int:pk>/",
        VehicleDocumentDetailView.as_view(),
        name="vehicle-document-detail",
    ),
]