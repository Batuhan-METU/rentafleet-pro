"""Şirket ayarları görünümü."""
from __future__ import annotations

from django.db.models import Count
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.companies.models import Company
from backend.common.permissions import IsFleetManager
from backend.apps.companies.serializers import CompanySerializer, CompanySettingsSerializer
from backend.common.multitenancy_tools.branding import company_branding_payload
from backend.common.multitenancy_tools.scope import require_user_company


class CompanySettingsView(APIView):
    """GET/PATCH /api/company/settings/ — şirket profili ve marka ayarları."""

    permission_classes = (IsFleetManager,)

    def _company(self, request: Request) -> Company:
        return require_user_company(request)

    def get(self, request: Request) -> Response:
        company = self._company(request)
        enriched = (
            Company.objects.filter(pk=company.pk)
            .annotate(vehicle_count=Count("vehicles"))
            .first()
        )
        data = CompanySerializer(enriched).data
        data["branding"] = company_branding_payload(company)
        return Response(data)

    def patch(self, request: Request) -> Response:
        company = self._company(request)

        serializer = CompanySettingsSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        enriched = (
            Company.objects.filter(pk=company.pk)
            .annotate(vehicle_count=Count("vehicles"))
            .first()
        )
        data = CompanySerializer(enriched).data
        data["branding"] = company_branding_payload(company)
        return Response(data)
