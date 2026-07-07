"""Şirket (tenant) serializer'ları."""

from __future__ import annotations

from rest_framework import serializers

from backend.models import Company


class CompanySerializer(serializers.ModelSerializer):
    """Serializes a tenant company plus a cheap derived fleet size."""

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
            "vehicle_count",
            "created_at",
        )
        read_only_fields = fields
