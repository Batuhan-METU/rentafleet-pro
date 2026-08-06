"""Karar destek ve müşteri profil serializer'ları."""

from __future__ import annotations

from rest_framework import serializers

from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import (
    CustomerFinancialProfile,
    CustomerIdentityProfile,
    CustomerLicenseProfile,
)


def _has_valid_turkish_national_id_checksum(digits: list[int]) -> bool:
    """T.C. kimlik no sağlama algoritması (resmi, kamuya açık algoritma).

    10. hane: (1,3,5,7,9. hanelerin toplamı × 7 − 2,4,6,8. hanelerin toplamı) mod 10
    11. hane: ilk 10 hanenin toplamının mod 10'u
    """
    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])
    tenth_ok = (odd_sum * 7 - even_sum) % 10 == digits[9]
    eleventh_ok = sum(digits[0:10]) % 10 == digits[10]
    return tenth_ok and eleventh_ok



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

    def validate_national_id(self, value: str) -> str:
        # Format kontrolü her zaman uygulanır — 11 haneli, 0 ile başlamayan
        # sayı (T.C. kimlik no ve Türkiye'deki yabancı kimlik numarası
        # ikisi de bu şekle sahip).
        if not value.isdigit() or len(value) != 11 or value[0] == "0":
            raise serializers.ValidationError(
                "Kimlik numarası 0 ile başlamayan 11 haneli bir sayı olmalıdır."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        # Sağlama (checksum) algoritması SADECE T.C. vatandaşları için
        # geçerlidir — yabancı uyruklu sürücülerin kimlik numarası farklı
        # (ve burada doğrulamadığımız) bir kurala göre üretilir, bu yüzden
        # `is_foreign=True` iken checksum'a bakılmaz, sadece format kontrolü
        # (validate_national_id) uygulanır.
        national_id = attrs.get("national_id")
        is_foreign = attrs.get("is_foreign", False)
        if national_id and not is_foreign:
            digits = [int(c) for c in national_id]
            if not _has_valid_turkish_national_id_checksum(digits):
                raise serializers.ValidationError(
                    {"national_id": "Geçersiz T.C. kimlik numarası (sağlama toplamı tutmuyor)."}
                )
        return attrs