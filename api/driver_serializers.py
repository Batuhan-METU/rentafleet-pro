"""DRF serializers — sürücü ve kiralama modelleri."""

from __future__ import annotations

from datetime import date

from rest_framework import serializers

from api.models import Driver, Rental, RentalStatus


class ActiveRentalSerializer(serializers.Serializer):
    """Sürücünün şu anki aktif kiralaması (varsa)."""

    rental_id = serializers.IntegerField()
    plaka = serializers.CharField()
    marka_model = serializers.CharField()
    guncel_km = serializers.IntegerField()
    enlem = serializers.FloatField(allow_null=True)
    boylam = serializers.FloatField(allow_null=True)
    baslangic_km = serializers.IntegerField()
    baslangic_tarihi = serializers.DateTimeField()


class DriverSerializer(serializers.ModelSerializer):
    """Sürücü listesi / detay — skor ve aktif kiralama view katmanında eklenir."""

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
            "is_blacklisted",
            "toplam_kiralama",
            "created_at",
        )
        read_only_fields = fields

    def get_yas(self, obj: Driver) -> int:
        today = date.today()
        born = obj.birth_date
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def get_toplam_kiralama(self, obj: Driver) -> int:
        return obj.rentals.exclude(status=RentalStatus.CANCELLED).count()
