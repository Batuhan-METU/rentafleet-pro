"""Kurumsal RBAC izin sınıfları (RentA-Fleet PRO — Day 13).

Single-tenant B2B panel: her kullanıcı tek bir kiralama şirketine bağlıdır.
İki rol vardır:

  * FLEET_MANAGER      — Filo Müdürü: tüm analitik, AI, fiyatlandırma, anomali.
  * OPERATIONS_STAFF   — Operasyon: araç listesi, canlı harita, bakım merkezi.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from api.models import UserRole


class IsFleetStaff(BasePermission):
    """Filo Müdürü veya Operasyon Personeli — temel operasyonel uçlar."""

    message = "Bu işlem için giriş yapmanız ve filo personeli olmanız gerekir."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role in (UserRole.FLEET_MANAGER, UserRole.OPERATIONS_STAFF)
        )


class IsFleetManager(BasePermission):
    """Yalnızca Filo Müdürü — finansal, AI ve güvenlik analitiği uçları."""

    message = "Bu alana yalnızca Filo Müdürü erişebilir."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == UserRole.FLEET_MANAGER
        )
