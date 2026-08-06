"""Kimlik doğrulama uçları."""

from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from backend.apps.companies.models import CustomUser
from backend.common.multitenancy_tools.branding import company_branding_payload


def _user_payload(user: CustomUser) -> dict:
    company = user.company if user.company_id else None
    branding = company_branding_payload(company)
    return {
        "id": user.pk,
        "username": user.get_username(),
        "full_name": user.get_full_name() or user.get_username(),
        "role": user.role,
        "role_display": user.get_role_display(),
        "company_id": user.company_id,
        "company_name": company.name if company else None,
        **branding,
        "branding": branding,
    }


class LoginView(APIView):
    permission_classes = (AllowAny,)
    # Genel "anon" limitinden (100/dk) ayrı, çok daha sıkı bir sınır — bu
    # endpoint kimlik doğrulaması OLMADAN çağrılabildiği için kaba kuvvet
    # denemelerine karşı en kritik nokta.
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"

    def post(self, request: Request) -> Response:
        username = request.data.get("username", "")
        password = request.data.get("password", "")

        if not isinstance(username, str) or not isinstance(password, str):
            return Response(
                {"error": "Kullanıcı adı ve şifre gereklidir."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username.strip(), password=password)
        if user is None or not isinstance(user, CustomUser):
            return Response(
                {"error": "Geçersiz kullanıcı adı veya şifre."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        company = getattr(request, "company", None)
        if company is not None and user.company_id != company.pk:
            return Response(
                {"error": "Bu alt alan adı üzerinden giriş izniniz bulunmamaktadır."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": _user_payload(user)})


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        if not isinstance(request.user, CustomUser):
            return Response({"error": "Geçersiz oturum."}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"user": _user_payload(request.user)})


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Oturum kapatıldı."})
