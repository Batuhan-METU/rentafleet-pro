from django.urls import path

from backend.apps.customer_profiles.views import (
    DriverCreateView,
    DriverDetailView,
    DriverListView,
    DriverRentalHistoryView,
    DriverScoreView,
)

urlpatterns = [
    path("drivers/", DriverListView.as_view(), name="driver-list"),
    path("drivers/create/", DriverCreateView.as_view(), name="driver-create"),
    path("drivers/<int:pk>/", DriverDetailView.as_view(), name="driver-detail"),
    path("drivers/<int:pk>/driver-score/", DriverScoreView.as_view(), name="driver-score"),
    path("drivers/<int:pk>/rentals/", DriverRentalHistoryView.as_view(), name="driver-rentals"),
]