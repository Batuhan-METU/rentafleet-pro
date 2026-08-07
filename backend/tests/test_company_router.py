"""CompanyRouterMiddleware'in şirket çözümleme mantığı için regresyon testleri.

Kapsam: audit sırasında bulunan iki gerçek hata —
1. Öneki (prefix) eşleşmesi tam eşleşmeden önceliklendirilmiş olabiliyordu
   ("acme" / "acmecorp" gibi durumlarda yanlış şirket seçilebiliyordu).
2. `?company=`/`X-Company-Slug` geliştirme geçişi DEBUG=False iken de
   çalışıyordu (üretimde şirket sahteciliğine izin verebilirdi).

Ve canlı Render dağıtımını bloke eden üçüncü, gerçek bir üretim hatası:
3. `<servis-adı>.onrender.com` de `acme.rentafleetpro.com` ile AYNI nokta
   sayısına sahip olduğu için ilk etiket ("servis-adı") yanlışlıkla bir
   kiracı subdomain'i sanılıyor, var olmayan bir şirket için 404
   ("Kayıtlı şirket bulunamadı.") dönüyordu — LoginView'a hiç ulaşılamıyordu.
"""

from __future__ import annotations

import pytest

from backend.apps.companies.models import Company
from backend.common.middleware.company_router import (
    _dev_company_slug,
    extract_subdomain,
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


def test_real_tenant_subdomain_still_detected():
    assert extract_subdomain("acme.rentafleetpro.com") == "acme"


def test_platform_root_domain_is_not_mistaken_for_a_tenant_subdomain(settings):
    # Render servis adı ("rentafleet-pro") nokta sayısı bakımından gerçek bir
    # kiracı subdomain'inden (ör. "acme.rentafleetpro.com") ayırt edilemez —
    # PLATFORM_ROOT_DOMAINS bu ayrımı açıkça yapar.
    settings.PLATFORM_ROOT_DOMAINS = ["onrender.com"]
    assert extract_subdomain("rentafleet-pro.onrender.com") is None
    assert extract_subdomain("any-other-service-name.onrender.com") is None


def test_bare_platform_root_domain_itself_is_not_a_subdomain(settings):
    settings.PLATFORM_ROOT_DOMAINS = ["onrender.com"]
    assert extract_subdomain("onrender.com") is None


def test_login_succeeds_on_a_platform_root_domain_host(client, company, manager, settings):
    """Uçtan uca regresyon: `rentafleet-pro.onrender.com` Host başlığıyla
    gelen bir giriş isteği, middleware'in 404'üne takılmadan LoginView'a
    ulaşmalı. `manager` fixture'ı `test-pass-123` şifresiyle oluşturulur
    (bkz. conftest.py)."""
    settings.PLATFORM_ROOT_DOMAINS = ["onrender.com"]
    settings.ALLOWED_HOSTS = ["*"]

    response = client.post(
        "/api/auth/login/",
        {"username": manager.username, "password": "test-pass-123"},
        format="json",
        HTTP_HOST="rentafleet-pro.onrender.com",
    )

    assert response.status_code == 200
    assert response.data["user"]["username"] == manager.username
