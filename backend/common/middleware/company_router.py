"""Subdomain tabanlı şirket (multi-tenant) tespiti.

Kurallar:
  * Host'ta subdomain var ve şirket yok → 404 (canlı güvenlik)
  * Düz localhost + ?company= → bilinmeyen slug yok sayılır (dev girişi bozulmaz)
"""

from __future__ import annotations

import re
from typing import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from backend.apps.companies.models import Company

_BARE_HOSTS = frozenset({"localhost", "127.0.0.1", "rentafleetpro.com", "www.rentafleetpro.com"})
_RESERVED = frozenset({"www", "api", "admin"})
_EXEMPT_PREFIXES = ("/admin/", "/api/health/", "/api/saas/")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower().strip())


def extract_subdomain(host: str) -> str | None:
    hostname = host.split(":")[0].lower().strip()
    if not hostname or hostname in _BARE_HOSTS:
        return None
    parts = hostname.split(".")
    if hostname.endswith(".localhost") and len(parts) >= 2:
        sub = parts[0]
        return sub if sub not in _RESERVED else None
    if len(parts) >= 3:
        sub = parts[0]
        return sub if sub not in _RESERVED else None
    return None


def company_matches_subdomain(company: Company, subdomain: str) -> bool:
    needle = subdomain.lower().strip()
    if not needle:
        return False
    if company.tax_number.lower() == needle:
        return True
    name = company.name.lower().strip()
    if name == needle:
        return True
    name_slug, needle_slug = _slugify(company.name), _slugify(needle)
    return name_slug == needle_slug or name_slug.startswith(needle_slug)


def resolve_company_by_subdomain(subdomain: str) -> Company | None:
    if not subdomain:
        return None
    for company in Company.objects.all().order_by("id"):
        if company_matches_subdomain(company, subdomain):
            return company
    return None


def _dev_company_slug(request: HttpRequest) -> str | None:
    """Düz localhost'ta ?company= veya X-Company-Slug (host subdomain değil)."""
    header = request.headers.get("X-Company-Slug", "").strip().lower()
    if header and header not in _RESERVED:
        return header
    query = request.GET.get("company", "").strip().lower()
    if query and query not in _RESERVED:
        return query
    return None


def _is_exempt(path: str) -> bool:
    return any(path.startswith(p) for p in _EXEMPT_PREFIXES)


class CompanyRouterMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if _is_exempt(request.path):
            request.company = None  # type: ignore[attr-defined]
            return self.get_response(request)

        host_slug = extract_subdomain(request.get_host())
        if host_slug:
            company = resolve_company_by_subdomain(host_slug)
            if company is None:
                return JsonResponse({"error": "Kayıtlı şirket bulunamadı."}, status=404)
            request.company = company  # type: ignore[attr-defined]
            return self.get_response(request)

        dev_slug = _dev_company_slug(request)
        request.company = resolve_company_by_subdomain(dev_slug) if dev_slug else None  # type: ignore[attr-defined]
        return self.get_response(request)
