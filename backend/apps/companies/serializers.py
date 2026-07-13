"""Şirket serializer'ları."""

from __future__ import annotations

from rest_framework import serializers

from backend.apps.companies.models import Company


class CompanySerializer(serializers.ModelSerializer):
    """Serializes a company plus a cheap derived fleet size."""

    vehicle_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "display_name",
            "logo_url",
            "primary_color",
            "secondary_color",
            "tax_number",
            "description",
            "vehicle_count",
            "created_at",
        )
        read_only_fields = fields


class CompanySettingsSerializer(serializers.ModelSerializer):
    """Şirket ayarları — müdür tarafından güncellenebilir alanlar."""

    class Meta:
        model = Company
        fields = (
            "display_name",
            "logo_url",
            "primary_color",
            "secondary_color",
            "description",
        )

    def validate_primary_color(self, value: str) -> str:
        if value and not (value.startswith("#") and len(value) == 7):
            raise serializers.ValidationError("Ana renk #RRGGBB formatında olmalıdır.")
        return value

    def validate_secondary_color(self, value: str) -> str:
        if value and not (value.startswith("#") and len(value) == 7):
            raise serializers.ValidationError("İkincil renk #RRGGBB formatında olmalıdır.")
        return value
