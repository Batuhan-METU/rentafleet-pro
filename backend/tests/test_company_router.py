"""CompanyRouterMiddleware'in şirket çözümleme mantığı için regresyon testleri.

Kapsam: audit sırasında bulunan iki gerçek hata —
1. Öneki (prefix) eşleşmesi tam eşleşmeden önceliklendirilmiş olabiliyordu
   ("acme" / "acmecorp" gibi durumlarda yanlış şirket seçilebiliyordu).
2. `?company=`/`X-Company-Slug` geliştirme geçişi DEBUG=False iken de
   çalışıyordu (üretimde şirket sahteciliğine izin verebilirdi).
"""

from __future__ import annotations

import pytest

from backend.apps.companies.models import Company
from backend.common.middleware.company_router import (
    _dev_company_slug,
    resolve_company_by_subdomain,
)

pytestmark = pytest.mark.django_db


class _FakeRequest:
    """`_dev_company_slug` yalnızca `.headers`/`.GET` okuduğu için minimal sahte istek."""

    def __init__(self, *, header: str = "", query: str = "") -> None:
        self.headers = {"X-Company-Slug": header} if header else {}
        self.GET = {"company": query} if query else {}


def test_exact_match_wins_over_ambiguous_prefix():
    # "acme" hem kendi başına bir şirket adı hem de "acmecorp"un öneki —
    # eski `startswith` taraması id sırasına göre yanlışını seçebiliyordu.
    acmecorp = Company.objects.create(name="Acmecorp", tax_number="1111111111")
    acme = Company.objects.create(name="Acme", tax_number="2222222222")
    assert acmecorp.id < acme.id  # id sırası kasıtlı olarak "yanlış" öneki önce koyar

    assert resolve_company_by_subdomain("acme") == acme
    assert resolve_company_by_subdomain("acmecorp") == acmecorp


def test_prefix_match_still_works_as_fallback_when_no_exact_match():
    company = Company.objects.create(name="Sensoy Rent A Car", tax_number="3333333333")
    # Tam eşleşme yok ("sensoy" tam ad değil) ama sluglaştırılmış önek eşleşiyor.
    assert resolve_company_by_subdomain("sensoy") == company


def test_unknown_subdomain_resolves_to_none():
    Company.objects.create(name="Acme", tax_number="4444444444")
    assert resolve_company_by_subdomain("does-not-exist") is None


def test_dev_company_slug_disabled_outside_debug(settings):
    settings.DEBUG = False
    assert _dev_company_slug(_FakeRequest(query="acme")) is None
    assert _dev_company_slug(_FakeRequest(header="acme")) is None


def test_dev_company_slug_enabled_in_debug(settings):
    settings.DEBUG = True
    assert _dev_company_slug(_FakeRequest(query="acme")) == "acme"
    assert _dev_company_slug(_FakeRequest(header="acme")) == "acme"
