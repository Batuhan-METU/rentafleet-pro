"""Oturum açmış filo kullanıcıları yalnızca kendi subdomain şirketine erişebilir."""

from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from backend.apps.companies.models import CustomUser
from backend.common.middleware.company_router import _EXEMPT_PREFIXES

_AUTH_EXEMPT = (
    "/api/auth/login/",
)


def _is_exempt(path: str) -> bool:
    if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
        return True
    return any(path.startswith(prefix) for prefix in _AUTH_EXEMPT)


class CompanyAccessMiddleware:
    """Authenticated fleet users must belong to the resolved company subdomain."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not _is_exempt(request.path):
            company = getattr(request, "company", None)
            user = request.user
            if (
                company is not None
                and user.is_authenticated
                and isinstance(user, CustomUser)
                and not user.is_superuser
                and user.company_id
                and user.company_id != company.pk
            ):
                return JsonResponse(
                    {"error": "Bu alt alan adı üzerinden erişim izniniz bulunmamaktadır."},
                    status=403,
                )
        return self.get_response(request)
