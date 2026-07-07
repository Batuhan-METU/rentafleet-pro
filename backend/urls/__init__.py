"""Root URL configuration for the RentA-Fleet PRO backend.

All application endpoints are mounted under ``/api/`` and delegated to the
versioned routers (``/api/v1/...``).
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("backend.urls.api")),
]
