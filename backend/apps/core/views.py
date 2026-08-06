"""Sağlık kontrolü ve hazırlık uçları."""

from __future__ import annotations

import logging

from django.db import connections
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.infrastructure.clickhouse.client import ping as clickhouse_ping

logger = logging.getLogger(__name__)


def _relational_db_ok() -> bool:
    """PostgreSQL/SQLite bağlantısını gerçekten dener — eskiden bu her zaman
    ``True`` sabitlenmişti (istek ORM'e ULAŞTI diye çalıştığı varsayılıyordu),
    bu yüzden veritabanı fiilen ÇÖKMÜŞ olsa bile health check "ok" derdi.
    Bu, tam olarak bir readiness probe'un yakalaması gereken senaryo —
    orkestratör (k8s/load balancer) trafiği bu instance'a göndermeye devam
    ederdi.
    """
    try:
        connections["default"].ensure_connection()
        return True
    except OperationalError:
        logger.exception("Health check: relational DB bağlantısı başarısız")
        return False


class HealthCheckView(APIView):
    """Readiness probe reporting reachability of both data stores."""

    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        relational_ok = _relational_db_ok()
        clickhouse_ok = clickhouse_ping()
        all_ok = relational_ok and clickhouse_ok
        payload = {
            "service": "rentafleet-pro",
            "version": request.version,
            "stores": {
                "relational": "ok" if relational_ok else "unavailable",
                "clickhouse": "ok" if clickhouse_ok else "unavailable",
            },
        }
        http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=http_status)