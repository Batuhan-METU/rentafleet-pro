"""Filo Müdürü personel yönetimi (multi-tenant)."""

from __future__ import annotations

from django.db import IntegrityError
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.models import CustomUser, UserRole
from backend.permissions import IsFleetManager


def _personnel_item(user: CustomUser) -> dict:
    return {
        "id": user.pk,
        "username": user.get_username(),
        "full_name": user.get_full_name() or user.get_username(),
        "role": user.role,
        "role_display": user.get_role_display(),
        "email": user.email or "",
    }


class PersonnelManagementView(APIView):
    """GET/POST /api/v1/personnel/ — müdürün kendi şirket personeli."""

    permission_classes = (IsFleetManager,)

    def get(self, request: Request) -> Response:
        users = (
            CustomUser.objects.filter(company=request.user.company)
            .order_by("username")
        )
        personnel = [_personnel_item(user) for user in users]
        return Response(
            {
                "personel_sayisi": len(personnel),
                "personeller": personnel,
            }
        )

    def post(self, request: Request) -> Response:
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        first_name = request.data.get("first_name", "")
        last_name = request.data.get("last_name", "")
        email = request.data.get("email", "")

        if not isinstance(username, str) or not username.strip():
            return Response(
                {"error": "Kullanıcı adı zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(password, str) or not password:
            return Response(
                {"error": "Şifre zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        manager_company = request.user.company
        if manager_company is None:
            return Response(
                {"error": "Şirket bilgisi bulunamadı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = CustomUser.objects.create_user(
                username=username.strip(),
                password=password,
                first_name=str(first_name).strip() if first_name else "",
                last_name=str(last_name).strip() if last_name else "",
                email=str(email).strip() if email else "",
                company=manager_company,
                role=UserRole.OPERATIONS_STAFF,
            )
        except IntegrityError:
            return Response(
                {"error": "Bu kullanıcı adı zaten kullanılıyor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "mesaj": "Operasyon personeli başarıyla oluşturuldu.",
                "personel": _personnel_item(user),
            },
            status=status.HTTP_201_CREATED,
        )
