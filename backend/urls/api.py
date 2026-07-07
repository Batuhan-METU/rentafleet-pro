"""API entrypoint URL configuration.

Dispatches by version so each API generation lives in its own isolated
module (``backend/urls/v1.py``). Adding ``v2`` later is purely additive — no
existing route changes. Combined with DRF's ``URLPathVersioning``, the
matched ``version`` is also exposed on ``request.version`` inside views.
"""

from django.urls import include, path

urlpatterns = [
    path("v1/", include(("backend.urls.v1", "v1"), namespace="v1")),
]
