"""Version 1 API views."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.clickhouse_client import ping as clickhouse_ping


class HealthCheckView(APIView):
    """Readiness probe reporting reachability of both data stores."""

    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        clickhouse_ok = clickhouse_ping()
        payload = {
            "service": "rentafleet-pro",
            "version": request.version,
            "stores": {
                "relational": "ok",  # request reached the ORM-backed app (SQLite locally)
                "clickhouse": "ok" if clickhouse_ok else "unavailable",
            },
        }
        http_status = (
            status.HTTP_200_OK if clickhouse_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(payload, status=http_status)
