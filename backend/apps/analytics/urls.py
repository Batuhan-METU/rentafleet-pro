from django.urls import path

from backend.apps.analytics.views import CompanyOverviewView

urlpatterns = [
    path("fleet/overview/", CompanyOverviewView.as_view(), name="fleet-overview"),
]