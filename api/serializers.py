"""DRF serializers for the relational (SQLite/PostgreSQL) domain models."""

from __future__ import annotations

from rest_framework import serializers

from api.models import Company, CompetitorPrice, Vehicle
from api.services.sipp_service import (
    decode_sipp,
    format_marka_model_sinif,
    resolve_sipp,
    sipp_detay_metni,
)


class CompanySerializer(serializers.ModelSerializer):
    """Serializes a tenant company plus a cheap derived fleet size."""

    vehicle_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "tax_number",
            "vehicle_count",
            "created_at",
        )
        read_only_fields = fields


class VehicleSerializer(serializers.ModelSerializer):
    """Serializes a fleet vehicle with SIPP segment and Turkish status labels."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    sinif_etiketi = serializers.SerializerMethodField()
    marka_model_sinif = serializers.SerializerMethodField()
    sipp_detay = serializers.SerializerMethodField()
    sipp_ozellikler = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "plate_number",
            "brand",
            "model",
            "sipp_code",
            "sinif_etiketi",
            "marka_model_sinif",
            "sipp_detay",
            "sipp_ozellikler",
            "production_year",
            "current_km",
            "status",
            "status_display",
            "company",
            "company_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def _profile(self, obj: Vehicle):
        return resolve_sipp(obj.brand, obj.model, obj.sipp_code or None)

    def get_sinif_etiketi(self, obj: Vehicle) -> str:
        return self._profile(obj).segment_label

    def get_marka_model_sinif(self, obj: Vehicle) -> str:
        return format_marka_model_sinif(obj.brand, obj.model, obj.sipp_code)

    def get_sipp_detay(self, obj: Vehicle) -> str:
        return sipp_detay_metni(self._profile(obj).code)

    def get_sipp_ozellikler(self, obj: Vehicle) -> dict[str, str]:
        return decode_sipp(self._profile(obj).code)


class CompetitorPriceSerializer(serializers.ModelSerializer):
    """Rakip kaynak günlük fiyatı — API yanıtı Türkçe alan adlarıyla."""

    kaynak = serializers.SerializerMethodField()
    gunluk_fiyat = serializers.DecimalField(
        source="daily_price", max_digits=10, decimal_places=2
    )
    benzer_arac = serializers.CharField(source="similar_vehicle", read_only=True)
    guncellendi = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = CompetitorPrice
        fields = ("id", "kaynak", "benzer_arac", "gunluk_fiyat", "guncellendi")
        read_only_fields = ("id", "guncellendi")

    def get_kaynak(self, obj: CompetitorPrice) -> str:
        return (obj.provider_name or obj.source_name or "").strip()
