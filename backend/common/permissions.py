"""Kurumsal RBAC izin sınıfları (RentA-Fleet PRO).

Multi-tenant shared DB: her filo kullanıcısı tek bir ``Company`` şirketine bağlıdır.
Subdomain veya ``?company=`` ile çözümlenen şirket, oturum açmış kullanıcının
şirketiyle eşleşmelidir (``CompanyAccessMiddleware`` + login kontrolü).

Roller:

  * FLEET_MANAGER      — Filo Müdürü: tüm analitik, AI, fiyatlandırma, anomali.
  * OPERATIONS_STAFF   — Operasyon: araç listesi, canlı harita, bakım merkezi.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.apps.companies.models import CustomUser, UserRole
from backend.common.multitenancy_tools.scope import user_matches_company


def _fleet_user_ok(request: Request, user: CustomUser) -> bool:
    return bool(user.company_id and user_matches_company(request))


class IsFleetStaff(BasePermission):
    """Filo Müdürü veya Operasyon Personeli — temel operasyonel uçlar."""

    message = "Bu işlem için giriş yapmanız ve filo personeli olmanız gerekir."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and isinstance(user, CustomUser)
            and user.role in (UserRole.FLEET_MANAGER, UserRole.OPERATIONS_STAFF)
            and _fleet_user_ok(request, user)
        )


class IsFleetManager(BasePermission):
    """Yalnızca Filo Müdürü — finansal, AI ve güvenlik analitiği uçları."""

    message = "Bu alana yalnızca Filo Müdürü erişebilir."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and isinstance(user, CustomUser)
            and user.role == UserRole.FLEET_MANAGER
            and _fleet_user_ok(request, user)
        )


class IsSuperUser(BasePermission):
    """Platform süper admini — SaaS şirket kurulumu vb."""

    message = "Bu işlem yalnızca süper admin yetkisiyle yapılabilir."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)
