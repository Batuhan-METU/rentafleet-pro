"""Filo analitik görünümleri."""
from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.infrastructure.services.analytics.company_overview_service import get_company_overview
from backend.infrastructure.services.analytics.return_stats_service import get_return_stats
from backend.common.permissions import IsFleetManager
from backend.common.multitenancy_tools.scope import require_user_company


def _parse_year(request: Request) -> int | None:
    raw_year = request.query_params.get("yil")
    if raw_year is None:
        return None
    try:
        return int(raw_year)
    except (TypeError, ValueError):
        return None


class CompanyOverviewView(APIView):
    """GET /api/fleet/overview/ — şirket künyesi ve finansal KPI'lar."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)
        return Response(get_company_overview(company.pk, year=_parse_year(request)))


class ReturnStatsView(APIView):
    """GET /api/fleet/return-stats/ — teslimat durum dağılımı + erken/geç finansal fark."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)
        return Response(get_return_stats(company.pk, year=_parse_year(request)))