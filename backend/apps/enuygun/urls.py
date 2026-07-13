from django.urls import path

from backend.apps.enuygun.views import FleetCompetitorPricesView, VehicleCompetitorPriceView

urlpatterns = [
    path(
        "vehicles/<int:pk>/competitor-prices/",
        VehicleCompetitorPriceView.as_view(),
        name="vehicle-competitor-prices",
    ),
    path(
        "fleet/competitor-prices/",
        FleetCompetitorPricesView.as_view(),
        name="fleet-competitor-prices",
    ),
]