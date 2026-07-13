"""Sürücü serializer'ları."""

from __future__ import annotations

from datetime import date

from rest_framework import serializers

from backend.apps.customer_profiles.models import Driver
from backend.apps.reservations.models import RentalStatus
from backend.apps.risk_checks.serializers import (
    CustomerFinancialSerializer,
    CustomerIdentitySerializer,
    CustomerLicenseSerializer,
    DriverCreateSerializer,
)


class DriverCreateRequestSerializer(serializers.Serializer):
    driver = DriverCreateSerializer()
    identity = CustomerIdentitySerializer(required=False)
    license = CustomerLicenseSerializer(required=False)
    financial = CustomerFinancialSerializer(required=False)


class DriverSerializer(serializers.ModelSerializer):
    """Sürücü listesi / detay — risk ve araç uygunluğu view katmanında eklenir."""

    ad_soyad = serializers.CharField(source="full_name", read_only=True)
    yas = serializers.SerializerMethodField()
    cinsiyet = serializers.CharField(source="get_gender_display", read_only=True)
    toplam_kiralama = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = (
            "id",
            "ad_soyad",
            "first_name",
            "last_name",
            "national_id",
            "yas",
            "cinsiyet",
            "gender",
            "birth_date",
            "phone",
            "email",
            "license_number",
            "license_class",
            "city",
            "district",
            "address",
            "occupation",
            "employer",
            "monthly_income",
            "is_blacklisted",
            "toplam_kiralama",
            "current_risk_score",
            "risk_note",
            "created_at",
        )
        read_only_fields = fields

    def get_yas(self, obj: Driver) -> int:
        today = date.today()
        born = obj.birth_date
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def get_toplam_kiralama(self, obj: Driver) -> int:
        return obj.rentals.exclude(status=RentalStatus.CANCELLED).count()