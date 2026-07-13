"""Filo analitik görünümleri."""
from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.infrastructure.services.analytics.company_overview_service import get_company_overview
from backend.common.permissions import IsFleetManager
from backend.common.multitenancy_tools.scope import require_user_company


class CompanyOverviewView(APIView):
    """GET /api/fleet/overview/ — şirket künyesi ve finansal KPI'lar."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        company = require_user_company(request)
        company_id = company.pk
        year = None
        raw_year = request.query_params.get("yil")
        if raw_year is not None:
            try:
                year = int(raw_year)
            except (TypeError, ValueError):
                year = None
        return Response(get_company_overview(company_id, year=year))