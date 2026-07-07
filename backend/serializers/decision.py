"""Karar destek ve müşteri profil serializer'ları."""

from __future__ import annotations

from rest_framework import serializers

from backend.models import (
    CustomerFinancialProfile,
    CustomerIdentityProfile,
    CustomerLicenseProfile,
    Driver,
    RentalApplication,
    RentalDecisionLog,
)


class CustomerIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerIdentityProfile
        fields = (
            "identity_verified",
            "phone_verified",
            "email_verified",
            "passport_number",
            "document_fraud_suspicion",
            "manual_notes",
        )


class CustomerLicenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerLicenseProfile
        fields = (
            "license_issue_date",
            "license_points",
            "license_penalty_count",
            "has_src_certificate",
            "has_psychotechnical",
        )


class CustomerFinancialSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerFinancialProfile
        fields = (
            "findeks_score",
            "credit_debt_amount",
            "has_enforcement_record",
            "bank_blacklist_flag",
            "payment_delay_count",
            "fraud_suspicion",
            "reference_status",
        )


class DriverCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = (
            "first_name",
            "last_name",
            "national_id",
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
            "marital_status",
            "children_count",
            "education_level",
            "citizenship",
            "is_foreign",
            "residence_duration_months",
        )


class RentalApplicationSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source="driver.full_name", read_only=True)

    class Meta:
        model = RentalApplication
        fields = (
            "id",
            "driver",
            "driver_name",
            "status",
            "is_first_rental",
            "requested_pickup_at",
            "requested_return_at",
            "assigned_vehicle",
            "risk_score",
            "risk_level",
            "deposit_amount",
            "quoted_total",
            "rejection_reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "is_first_rental",
            "risk_score",
            "risk_level",
            "deposit_amount",
            "quoted_total",
            "rejection_reason",
            "created_at",
            "updated_at",
        )


class RentalApplicationCreateSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField(required=False)
    driver = DriverCreateSerializer(required=False)
    identity = CustomerIdentitySerializer(required=False)
    license = CustomerLicenseSerializer(required=False)
    financial = CustomerFinancialSerializer(required=False)
    requested_pickup_at = serializers.DateTimeField(required=False, allow_null=True)
    requested_return_at = serializers.DateTimeField(required=False, allow_null=True)


class RentalDecisionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalDecisionLog
        fields = (
            "id",
            "step",
            "engine",
            "score",
            "risk_level",
            "approved",
            "output_snapshot",
            "created_at",
        )
