from django.urls import path

from backend.apps.analytics.views import CompanyOverviewView, ReturnStatsView

urlpatterns = [
    path("fleet/overview/", CompanyOverviewView.as_view(), name="fleet-overview"),
    path("fleet/return-stats/", ReturnStatsView.as_view(), name="fleet-return-stats"),
]