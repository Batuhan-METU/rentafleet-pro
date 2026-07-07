"""Araç ve rakip fiyat serializer'ları."""

from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from backend.models import Company, CompetitorPrice, Vehicle, VehicleFinancialProfile
from backend.serializers.finance import VehicleFinancialProfileSerializer
from backend.infrastructure.services.sipp.sipp_service import (
    decode_sipp,
    format_marka_model_sinif,
    resolve_sipp,
    sipp_detay_metni,
)


class VehicleSerializer(serializers.ModelSerializer):
    """Serializes a fleet vehicle with SIPP segment and Turkish status labels."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    sinif_etiketi = serializers.SerializerMethodField()
    marka_model_sinif = serializers.SerializerMethodField()
    sipp_detay = serializers.SerializerMethodField()
    sipp_ozellikler = serializers.SerializerMethodField()

    has_financial_profile = serializers.SerializerMethodField()

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
            "package",
            "fuel_type",
            "transmission",
            "engine_displacement_cc",
            "engine_power_hp",
            "segment",
            "body_type",
            "color",
            "chassis_number",
            "registration_number",
            "purchase_price",
            "initial_industrial_expense",
            "annual_kasko_cost",
            "annual_traffic_insurance_cost",
            "annual_insurance_cost",
            "annual_mtv_cost",
            "estimated_monthly_maintenance",
            "annual_inspection_cost",
            "fuel_tank_capacity_liters",
            "target_monthly_km",
            "has_financial_profile",
            "company",
            "company_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_has_financial_profile(self, obj: Vehicle) -> bool:
        return VehicleFinancialProfile.objects.filter(vehicle=obj).exists()

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


class VehicleWriteSerializer(serializers.ModelSerializer):
    """Araç oluşturma/güncelleme — künye + iç içe finansal profil.

    Tek ekranda araç künyesi ve satın alma/kiralama planı birlikte kaydedilir.
    ``company`` gövdede verilmezse view kullanıcının şirketini atar.
    """

    financial_profile = VehicleFinancialProfileSerializer(required=False)
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), required=False
    )

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "plate_number",
            "brand",
            "model",
            "sipp_code",
            "production_year",
            "current_km",
            "status",
            "package",
            "fuel_type",
            "transmission",
            "engine_displacement_cc",
            "engine_power_hp",
            "segment",
            "body_type",
            "color",
            "chassis_number",
            "registration_number",
            "purchase_price",
            "initial_industrial_expense",
            "annual_kasko_cost",
            "annual_traffic_insurance_cost",
            "annual_insurance_cost",
            "annual_mtv_cost",
            "estimated_monthly_maintenance",
            "annual_inspection_cost",
            "fuel_tank_capacity_liters",
            "target_monthly_km",
            "company",
            "financial_profile",
        )
        read_only_fields = ("id",)

    def _sync_tco_fields(self, vehicle: Vehicle, profile_data: dict | None) -> None:
        """Vehicle TCO alanları ile finansal profil satın alma fiyatını eşitle."""
        if profile_data is None:
            return
        profile_price = profile_data.get("purchase_price")
        if profile_price and not vehicle.purchase_price:
            vehicle.purchase_price = profile_price
            vehicle.save(update_fields=["purchase_price"])
        elif vehicle.purchase_price and not profile_price:
            profile_data.setdefault("purchase_price", vehicle.purchase_price)

    @transaction.atomic
    def create(self, validated_data: dict) -> Vehicle:
        profile_data = validated_data.pop("financial_profile", None)
        vehicle = Vehicle.objects.create(**validated_data)
        if profile_data:
            self._sync_tco_fields(vehicle, profile_data)
            VehicleFinancialProfile.objects.create(vehicle=vehicle, **profile_data)
        return vehicle

    @transaction.atomic
    def update(self, instance: Vehicle, validated_data: dict) -> Vehicle:
        profile_data = validated_data.pop("financial_profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data is not None:
            self._sync_tco_fields(instance, profile_data)
            VehicleFinancialProfile.objects.update_or_create(
                vehicle=instance, defaults=profile_data
            )
        return instance

    def to_representation(self, instance: Vehicle) -> dict:
        # Yazma sonrası zengin okuma temsili döndür.
        data = VehicleSerializer(instance, context=self.context).data
        try:
            data["financial_profile"] = VehicleFinancialProfileSerializer(
                instance.financial_profile
            ).data
        except VehicleFinancialProfile.DoesNotExist:
            data["financial_profile"] = None
        from backend.infrastructure.services.pricing.rental_economics_service import build_maliyet_analizi_payload

        analysis = build_maliyet_analizi_payload(instance)
        if analysis:
            data["maliyet_analizi"] = analysis
        return data
