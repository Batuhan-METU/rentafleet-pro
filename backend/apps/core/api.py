"""Kök URL yapılandırması — /admin ve /api uçları."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("backend.apps.core.urls")),
    path("api/", include("backend.apps.companies.urls")),
    path("api/", include("backend.apps.vehicles.urls")),
    path("api/", include("backend.apps.customer_profiles.urls")),
    path("api/", include("backend.apps.reservations.urls")),
    path("api/", include("backend.apps.floor_pricing.urls")),
    path("api/", include("backend.apps.enuygun.urls")),
    path("api/", include("backend.apps.analytics.urls")),
    path("api/", include("backend.apps.ai.urls")),
]
