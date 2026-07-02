"""Kimlik doğrulama uçları (RentA-Fleet PRO — Day 13).

Token tabanlı giriş; Vue SPA Authorization başlığı ile istek gönderir.
"""

from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import CustomUser


def _user_payload(user: CustomUser) -> dict:
    """Oturum açmış kullanıcıyı frontend'in tüketebileceği sözlüğe çevirir."""
    return {
        "id": user.pk,
        "username": user.get_username(),
        "full_name": user.get_full_name() or user.get_username(),
        "role": user.role,
        "role_display": user.get_role_display(),
        "company_name": user.company.name if user.company_id else None,
    }


class LoginView(APIView):
    """POST /api/v1/auth/login/ — kullanıcı adı + şifre ile token al."""

    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        username = request.data.get("username", "")
        password = request.data.get("password", "")

        if not isinstance(username, str) or not isinstance(password, str):
            return Response(
                {"error": "Kullanıcı adı ve şifre gereklidir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request,
            username=username.strip(),
            password=password,
        )
        if user is None:
            return Response(
                {"error": "Geçersiz kullanıcı adı veya şifre."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _created = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user": _user_payload(user),
            }
        )


class MeView(APIView):
    """GET /api/v1/auth/me/ — oturum açmış kullanıcının profil bilgisi."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        user = request.user
        if not isinstance(user, CustomUser):
            return Response(
                {"error": "Geçersiz kullanıcı oturumu."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"user": _user_payload(user)})


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — sunucu tarafı token'ı siler."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Oturum kapatıldı."})
