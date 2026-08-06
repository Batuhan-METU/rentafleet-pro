"""Araç ve rakip fiyat serializer'ları."""

from __future__ import annotations

import os

from django.db import transaction
from rest_framework import serializers

from backend.apps.enuygun.models import CompetitorPrice
from backend.apps.vehicle_finance.choices import ExpenseCategory, InsurancePolicyType
from backend.apps.vehicle_finance.models import (
    InsurancePolicy,
    VehicleExpense,
    VehicleFinancialProfile,
)
from backend.apps.vehicle_finance.serializers import (
    InsurancePolicySerializer,
    VehicleExpenseSerializer,
    VehicleFinancialProfileSerializer,
)
from backend.apps.vehicles.models import Vehicle, VehicleDocument, VehicleRegistrationDetail
from backend.infrastructure.services.sipp.sipp_service import (
    decode_sipp,
    format_brand_model_segment,
    resolve_sipp,
    sipp_detail_text,
)


class VehicleSerializer(serializers.ModelSerializer):
    """Serializes a fleet vehicle with SIPP segment and Turkish status labels."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    segment_label = serializers.SerializerMethodField()
    brand_model_segment = serializers.SerializerMethodField()
    sipp_detail = serializers.SerializerMethodField()
    sipp_attributes = serializers.SerializerMethodField()

    has_financial_profile = serializers.SerializerMethodField()
    financing_type = serializers.SerializerMethodField()
    financing_type_display = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "plate_number",
            "brand",
            "model",
            "sipp_code",
            "segment_label",
            "brand_model_segment",
            "sipp_detail",
            "sipp_attributes",
            "production_year",
            "current_km",
            "status",
            "status_display",
            "fleet_entry_date",
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
            "branch_name",
            "purchase_invoice_date",
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
            "financing_type",
            "financing_type_display",
            "company",
            "company_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_has_financial_profile(self, obj: Vehicle) -> bool:
        # Liste view'ları ``has_financial_profile_annotated`` ile önceden
        # tek sorguda hesaplar (bkz. ``scoped_vehicles_with_financial_flag``);
        # o alan yoksa (tekil nesne) doğrudan sorgulanır.
        annotated = getattr(obj, "has_financial_profile_annotated", None)
        if annotated is not None:
            return bool(annotated)
        return VehicleFinancialProfile.objects.filter(vehicle=obj).exists()

    def get_financing_type(self, obj: Vehicle) -> str | None:
        try:
            return obj.financial_profile.financing_type
        except VehicleFinancialProfile.DoesNotExist:
            return None

    def get_financing_type_display(self, obj: Vehicle) -> str | None:
        try:
            return obj.financial_profile.get_financing_type_display()
        except VehicleFinancialProfile.DoesNotExist:
            return None

    def _profile(self, obj: Vehicle):
        return resolve_sipp(obj.brand, obj.model, obj.sipp_code or None)

    def get_segment_label(self, obj: Vehicle) -> str:
        return self._profile(obj).segment_label

    def get_brand_model_segment(self, obj: Vehicle) -> str:
        return format_brand_model_segment(obj.brand, obj.model, obj.sipp_code)

    def get_sipp_detail(self, obj: Vehicle) -> str:
        return sipp_detail_text(self._profile(obj).code)

    def get_sipp_attributes(self, obj: Vehicle) -> dict[str, str]:
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


class VehicleInsurancePolicyInputSerializer(serializers.Serializer):
    """Araç formundan gelen tek bir poliçe girdisi (yazma-amaçlı, iç içe).

    Poliçe CRUD'u artık bağımsız bir "Poliçe Ekle" ekranından değil,
    doğrudan araç oluşturma/düzenleme formundan besleniyor — bkz.
    ``VehicleWriteSerializer.create``/``update``.
    """

    policy_type = serializers.ChoiceField(choices=InsurancePolicyType.choices)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    start_date = serializers.DateField()
    end_date = serializers.DateField()


class VehicleOperatingExpenseInputSerializer(serializers.Serializer):
    """Araç formundan gelen tek bir operasyon gideri girdisi (yazma-amaçlı,
    iç içe) — "Giderler" adımının "Operasyon" bölümünden beslenir. Sigorta
    poliçelerinden farklı olarak tip başına tek kayıt değildir (bir aracın
    onlarca ayrı bakım/lastik/hasar kaydı olabilir); her gönderilen satır
    AYRI bir ``VehicleExpense`` kaydı olarak eklenir, mevcutların üzerine
    yazılmaz (bkz. ``operating_expense_service`` — bu bileşen §3.5'in TEK
    veri kaynağı, ``Vehicle`` üzerindeki eski/kullanılmayan tahmini alanlar
    DEĞİL). ``odometer_km`` diğer kategorilerde opsiyoneldir, ama
    ``VEHICLE_MAINTENANCE`` ("Araç Bakım") için ZORUNLUDUR — Bakım
    Merkezi'nin "son bakım km"si TEK KAYNAĞI budur (bkz.
    maintenance_service.py); km bilinmeden girilen bir bakım kaydı, km
    boyutunu kalıcı olarak "bilinmiyor"a düşürür. ``income_amount``/
    ``income_source`` opsiyoneldir — bu gidere bağlı bir geri kazanım/
    tahsilat varsa (ör. sigorta tazminatı) buraya girilir; "Operasyon Gider
    Kırılımı" ekranındaki kategori bazlı Gelir/Gider/Fark bundan beslenir."""

    category = serializers.ChoiceField(choices=ExpenseCategory.choices)
    custom_label = serializers.CharField(required=False, allow_blank=True, default="")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    expense_date = serializers.DateField()
    odometer_km = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    income_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, default=None
    )
    income_source = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs: dict) -> dict:
        if attrs.get("category") == ExpenseCategory.VEHICLE_MAINTENANCE and attrs.get("odometer_km") is None:
            raise serializers.ValidationError(
                {"odometer_km": "Araç Bakım gideri için kilometre girilmesi zorunludur."}
            )
        return attrs


class VehicleRegistrationDetailSerializer(serializers.ModelSerializer):
    """FYS ruhsat/katalog sihirbazının ek alanları — tamamı opsiyonel,
    ruhsat verisi aşamalı girilebilir."""

    class Meta:
        model = VehicleRegistrationDetail
        exclude = ("id", "vehicle", "created_at", "updated_at")


class VehicleWriteSerializer(serializers.ModelSerializer):
    """Araç oluşturma/güncelleme — künye + iç içe finansal profil + poliçeler.

    Tek ekranda araç künyesi, satın alma/kiralama planı ve sigorta
    poliçeleri birlikte kaydedilir. ``company`` view tarafından
    kullanıcının kiracısı olarak atanır.
    """

    financial_profile = VehicleFinancialProfileSerializer(required=False)
    insurance_policies = VehicleInsurancePolicyInputSerializer(
        many=True, required=False, write_only=True
    )
    operating_expenses = VehicleOperatingExpenseInputSerializer(
        many=True, required=False, write_only=True
    )
    registration_detail = VehicleRegistrationDetailSerializer(required=False)

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
            "fleet_entry_date",
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
            "branch_name",
            "purchase_invoice_date",
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
            "financial_profile",
            "insurance_policies",
            "operating_expenses",
            "registration_detail",
        )
        read_only_fields = ("id", "current_km")

    def _enrich_derived_fields(self, validated_data: dict) -> None:
        """SIPP marka/model kataloğundan türetilir; km telemetriden gelir."""
        brand = validated_data.get("brand") or ""
        model = validated_data.get("model") or ""
        if not validated_data.get("sipp_code"):
            profile = resolve_sipp(brand, model, None)
            validated_data["sipp_code"] = profile.code

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

    def _sync_insurance_policies(self, vehicle: Vehicle, policies_data: list[dict] | None) -> None:
        """Formdan gelen poliçeleri (vehicle, policy_type) başına tek güncel
        kayıt olacak şekilde yazar — bkz. plan §3, gerçek dünyada bir aracın
        aktif olarak tek bir Kasko/Trafik/Yeşil Kart poliçesi olur."""
        if not policies_data:
            return
        for item in policies_data:
            InsurancePolicy.objects.update_or_create(
                vehicle=vehicle,
                policy_type=item["policy_type"],
                defaults={
                    "amount": item["amount"],
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
                },
            )

    def _create_operating_expenses(self, vehicle: Vehicle, expenses_data: list[dict] | None) -> None:
        """Formdan gelen operasyon giderlerini gerçek ``VehicleExpense``
        kayıtları olarak ekler. Poliçelerden farklı olarak tip başına tek
        kayıt DEĞİLDİR — her satır ayrı, kalıcı bir gider kaydıdır; mevcut
        kayıtların üzerine yazılmaz, sadece yeni girilenler eklenir."""
        if not expenses_data:
            return
        VehicleExpense.objects.bulk_create(
            VehicleExpense(vehicle=vehicle, **item) for item in expenses_data
        )

    @transaction.atomic
    def create(self, validated_data: dict) -> Vehicle:
        profile_data = validated_data.pop("financial_profile", None)
        policies_data = validated_data.pop("insurance_policies", None)
        expenses_data = validated_data.pop("operating_expenses", None)
        registration_data = validated_data.pop("registration_detail", None)
        self._enrich_derived_fields(validated_data)
        vehicle = Vehicle.objects.create(**validated_data)
        if profile_data:
            self._sync_tco_fields(vehicle, profile_data)
            VehicleFinancialProfile.objects.create(vehicle=vehicle, **profile_data)
        self._sync_insurance_policies(vehicle, policies_data)
        self._create_operating_expenses(vehicle, expenses_data)
        if registration_data:
            VehicleRegistrationDetail.objects.create(vehicle=vehicle, **registration_data)
        return vehicle

    @transaction.atomic
    def update(self, instance: Vehicle, validated_data: dict) -> Vehicle:
        profile_data = validated_data.pop("financial_profile", None)
        policies_data = validated_data.pop("insurance_policies", None)
        expenses_data = validated_data.pop("operating_expenses", None)
        registration_data = validated_data.pop("registration_detail", None)
        merged = {
            "brand": validated_data.get("brand", instance.brand),
            "model": validated_data.get("model", instance.model),
            "sipp_code": validated_data.get("sipp_code", instance.sipp_code),
        }
        if not validated_data.get("sipp_code"):
            profile = resolve_sipp(merged["brand"], merged["model"], None)
            validated_data["sipp_code"] = profile.code
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data is not None:
            self._sync_tco_fields(instance, profile_data)
            VehicleFinancialProfile.objects.update_or_create(
                vehicle=instance, defaults=profile_data
            )
        self._sync_insurance_policies(instance, policies_data)
        self._create_operating_expenses(instance, expenses_data)
        if registration_data is not None:
            VehicleRegistrationDetail.objects.update_or_create(
                vehicle=instance, defaults=registration_data
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
        data["insurance_policies"] = InsurancePolicySerializer(
            instance.insurance_policies.all(), many=True
        ).data
        data["operating_expenses"] = VehicleExpenseSerializer(
            instance.expenses.all(), many=True
        ).data
        try:
            data["registration_detail"] = VehicleRegistrationDetailSerializer(
                instance.registration_detail
            ).data
        except VehicleRegistrationDetail.DoesNotExist:
            data["registration_detail"] = None
        from backend.infrastructure.services.cost_calculation.rental_economics_service import (
            build_cost_analysis_payload,
        )

        analysis = build_cost_analysis_payload(instance)
        if analysis:
            data["cost_analysis"] = analysis
        return data


MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"})


def _validate_vehicle_document_file(value):
    """Sınırsız dosya yükleme (OWASP) korumaları — eskiden ``file`` alanında
    HİÇ boyut/tür kısıtı yoktu: herhangi bir tür/boyutta dosya (ör. bir
    yürütülebilir dosya ya da diski dolduracak kadar büyük bir dosya)
    kabul ediliyordu.
    """
    if value.size > MAX_DOCUMENT_SIZE_BYTES:
        raise serializers.ValidationError(
            f"Dosya çok büyük (maksimum {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MB)."
        )
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise serializers.ValidationError(
            f"Desteklenmeyen dosya türü ({ext or 'uzantısız'}). "
            f"İzin verilenler: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}."
        )
    return value


class VehicleDocumentSerializer(serializers.ModelSerializer):
    """"Dosyalar ve Ekler" — bir araca eklenmiş serbest dosya. ``file`` dışında
    tüm meta veriler (ad, boyut, tip, yükleyen) sunucu tarafında, gerçek
    yüklenen dosyadan türetilir — istemciden alınmaz."""

    uploaded_by_name = serializers.SerializerMethodField()
    file = serializers.FileField(validators=[_validate_vehicle_document_file])

    class Meta:
        model = VehicleDocument
        fields = (
            "id",
            "vehicle",
            "file",
            "label",
            "original_filename",
            "content_type",
            "size",
            "uploaded_at",
            "uploaded_by_name",
        )
        read_only_fields = (
            "vehicle",
            "original_filename",
            "content_type",
            "size",
            "uploaded_at",
        )

    def get_uploaded_by_name(self, obj: VehicleDocument) -> str | None:
        if not obj.uploaded_by:
            return None
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username