"""Kök URL yapılandırması — /admin ve /api uçları.

Not: bu dosya aynı zamanda Django'nun ROOT_URLCONF'u (bkz. backend/settings.py).
Kendi health/ ucunu da burada tanımlar, diğer app'lerin url.py'lerini include eder.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from backend.apps.core.views import HealthCheckView

urlpatterns = [
    path("api/health/", HealthCheckView.as_view(), name="health"),
    path("admin/", admin.site.urls),
    path("api/", include("backend.apps.companies.urls")),
    path("api/", include("backend.apps.vehicles.urls")),
    path("api/", include("backend.apps.customer_profiles.urls")),
    path("api/", include("backend.apps.rentals.urls")),
    path("api/", include("backend.apps.vehicle_finance.urls")),
    path("api/", include("backend.apps.enuygun.urls")),
    path("api/", include("backend.apps.analytics.urls")),
    path("api/", include("backend.apps.ai.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)