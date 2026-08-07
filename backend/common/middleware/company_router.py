"""Subdomain tabanlı şirket (multi-tenant) tespiti.

Kurallar:
  * Host'ta subdomain var ve şirket yok → 404 (canlı güvenlik)
  * Düz localhost + ?company= → bilinmeyen slug yok sayılır (dev girişi bozulmaz)
"""

from __future__ import annotations

import re
from collections.abc import Callable

from django.conf import settings
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
    # Render gibi PaaS'lerin kendi kök alan adı (settings.PLATFORM_ROOT_DOMAINS)
    # — "<servis-adı>.onrender.com" da tam olarak `.rentafleetpro.com` ile aynı
    # nokta-sayımına sahip ("3 parça") ama ilk etiket bir kiracı subdomain'i
    # DEĞİL, servisin kendi adıdır. Bu kontrol olmadan servis adı yanlışlıkla
    # bir kiracı subdomain'i sanılıp var olmayan bir şirket için 404 dönerdi.
    if any(hostname == root or hostname.endswith(f".{root}") for root in settings.PLATFORM_ROOT_DOMAINS):
        return None
    parts = hostname.split(".")
    if hostname.endswith(".localhost") and len(parts) >= 2:
        sub = parts[0]
        return sub if sub not in _RESERVED else None
    if len(parts) >= 3:
        sub = parts[0]
        return sub if sub not in _RESERVED else None
    return None


def _exact_subdomain_match(company: Company, needle: str) -> bool:
    """Vergi no, tam ad veya sluglaştırılmış ad birebir eşleşiyor mu?"""
    if company.tax_number.lower() == needle:
        return True
    if company.name.lower().strip() == needle:
        return True
    return _slugify(company.name) == _slugify(needle)


def _prefix_subdomain_match(company: Company, needle: str) -> bool:
    """Geriye dönük uyumluluk: sluglaştırılmış ad, subdomain'in öneki mi?"""
    return _slugify(company.name).startswith(_slugify(needle))


def resolve_company_by_subdomain(subdomain: str) -> Company | None:
    """Alt alan adını şirkete çözer — önce TAM eşleşme, sonra önek eşleşmesi.

    İki geçişli olmasının nedeni: iki şirketten birinin sluğu diğerinin öneki
    olduğunda (ör. "acme" / "acmecorp") eski tek-geçişli `startswith` taraması
    `id` sırasına göre YANLIŞ şirketi seçebiliyordu — bu, "acme" subdomain'ine
    gelen bir kullanıcının "acmecorp" şirketine çözülüp giriş yapamamasına
    (veya başka bir şirketin marka bilgisini görmesine) yol açan gerçek bir
    hataydı. Tam eşleşme her zaman önceliklidir; önek eşleşmesi yalnızca hiç
    tam eşleşme yoksa devreye girer.
    """
    if not subdomain:
        return None
    needle = subdomain.lower().strip()
    if not needle:
        return None
    # Eşleştirme yalnızca tax_number/name'e baktığı için diğer sütunlar hiç
    # çekilmez — satır sayısı yine O(şirket sayısı) ama her satırın maliyeti
    # düşer. Gerçek O(1) çözüm (indekslenmiş bir `subdomain_slug` sütunu)
    # şema değişikliği + geriye dönük doldurma gerektirir; bu projenin
    # ölçeğinde (bkz. audit bulgusu #35) şimdilik gerekli değil.
    companies = list(Company.objects.only("id", "tax_number", "name").order_by("id"))
    for company in companies:
        if _exact_subdomain_match(company, needle):
            return company
    for company in companies:
        if _prefix_subdomain_match(company, needle):
            return company
    return None


def _dev_company_slug(request: HttpRequest) -> str | None:
    """Sadece DEBUG=True iken: düz localhost'ta ?company= veya X-Company-Slug.

    Üretimde (DEBUG=False) bu geçersizdir — aksi halde herhangi bir ziyaretçi
    ana alan adında (ör. rentafleetpro.com) bu parametre/header ile
    `request.company`'yi keyfi bir şirkete zorlayabilirdi (satır bazlı veri
    erişimini etkilemez — o her zaman `user.company`'ye bakar — ama sahte
    403'lere veya marka bilgisi sızıntısına yol açabilirdi).
    """
    if not settings.DEBUG:
        return None
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
