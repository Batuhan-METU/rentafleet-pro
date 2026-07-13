"""Şirket markalama ve SaaS yönetim görünümleri."""
from __future__ import annotations

import re

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.common.multitenancy_tools.branding import company_branding_payload
from backend.common.middleware.company_router import resolve_company_by_subdomain
from backend.apps.companies.models import (
    Company,
    CustomUser,
    UserRole,
)
from backend.common.permissions import IsSuperUser


class CompanyBrandingView(APIView):
    """GET /api/company/branding/ — subdomain şirketinin white-label kimliği."""

    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        company = getattr(request, "company", None)
        branding = company_branding_payload(company)
        return Response(
            {
                "company_id": company.pk if company else None,
                "company_slug": company.name if company else None,
                **branding,
            }
        )


_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_SUBDOMAIN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$")
_PRODUCTION_DOMAIN = "rentafleetpro.com"


def _require_str(data: dict, key: str) -> str | None:
    value = data.get(key, "")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


class CreateNewCompanyView(APIView):
    """POST /api/saas/companies/ — yeni şirket + ilk Filo Müdürü (süper admin)."""

    permission_classes = (IsSuperUser,)

    @transaction.atomic
    def post(self, request: Request) -> Response:
        data = request.data

        company_name = _require_str(data, "company_name")
        subdomain = _require_str(data, "subdomain")
        tax_number = _require_str(data, "tax_number")
        primary_color = _require_str(data, "primary_color") or "#3B82F6"
        secondary_color = _require_str(data, "secondary_color") or "#1E3A8A"
        manager_username = _require_str(data, "manager_username")
        manager_password = data.get("manager_password", "")
        manager_email = _require_str(data, "manager_email") or ""
        manager_first_name = _require_str(data, "manager_first_name") or ""
        manager_last_name = _require_str(data, "manager_last_name") or ""

        missing = [
            label
            for label, val in (
                ("company_name", company_name),
                ("subdomain", subdomain),
                ("tax_number", tax_number),
                ("manager_username", manager_username),
            )
            if not val
        ]
        if missing:
            return Response(
                {"error": f"Zorunlu alanlar eksik: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(manager_password, str) or not manager_password:
            return Response(
                {"error": "manager_password zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subdomain = subdomain.lower()
        if not _SUBDOMAIN.match(subdomain):
            return Response(
                {"error": "subdomain yalnızca küçük harf, rakam ve tire içerebilir."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if resolve_company_by_subdomain(subdomain):
            return Response(
                {"error": "Bu subdomain zaten kullanılıyor."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _HEX_COLOR.match(primary_color) or not _HEX_COLOR.match(secondary_color):
            return Response(
                {"error": "Renk kodları #RRGGBB formatında olmalıdır."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if CustomUser.objects.filter(username=manager_username).exists():
            return Response(
                {"error": "Bu müdür kullanıcı adı zaten kayıtlı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            company = Company.objects.create(
                name=subdomain,
                display_name=company_name,
                tax_number=tax_number,
                primary_color=primary_color,
                secondary_color=secondary_color,
            )
            manager = CustomUser.objects.create_user(
                username=manager_username,
                password=manager_password,
                email=manager_email,
                first_name=manager_first_name,
                last_name=manager_last_name,
                company=company,
                role=UserRole.FLEET_MANAGER,
            )
        except IntegrityError:
            return Response(
                {"error": "Vergi numarası veya subdomain benzersizlik ihlali."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login_host = f"{subdomain}.{_PRODUCTION_DOMAIN}"
        branding = company_branding_payload(company)

        return Response(
            {
                "mesaj": (
                    "Şirket ve Müdür hesabı başarıyla aktifleştirildi. "
                    f"Giriş Adresi: {login_host}"
                ),
                "giris_adresi": login_host,
                "giris_adresi_yerel": f"http://{subdomain}.localhost:5173",
                "company": {
                    "id": company.pk,
                    "subdomain": subdomain,
                    "display_name": company.display_name,
                    **branding,
                },
                "manager": {
                    "id": manager.pk,
                    "username": manager.get_username(),
                    "email": manager.email,
                    "role": manager.role,
                },
            },
            status=status.HTTP_201_CREATED,
        )
