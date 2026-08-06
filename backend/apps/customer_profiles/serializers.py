"""Sürücü serializer'ları."""

from __future__ import annotations

from datetime import date

from rest_framework import serializers

from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import RentalStatus
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

    full_name = serializers.CharField(read_only=True)
    age = serializers.SerializerMethodField()
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)
    total_rentals = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = (
            "id",
            "full_name",
            "first_name",
            "last_name",
            "national_id",
            "age",
            "gender_display",
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
            "total_rentals",
            "current_risk_score",
            "risk_level",
            "risk_note",
            "created_at",
        )
        read_only_fields = fields

    def get_age(self, obj: Driver) -> int:
        today = date.today()
        born = obj.birth_date
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def get_total_rentals(self, obj: Driver) -> int:
        # DriverListView.get_queryset() bunu `total_rentals_count` olarak
        # tek bir sorguda (JOIN+GROUP BY, N+1 önlenir) önceden hesaplar;
        # anotasyon yoksa (ör. tekil sürücü detayı) doğrudan sorgulanır.
        annotated = getattr(obj, "total_rentals_count", None)
        if annotated is not None:
            return annotated
        return obj.rentals.exclude(status=RentalStatus.CANCELLED).count()