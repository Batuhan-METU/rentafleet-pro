"""Kiralama / rezervasyon serializer'ları."""

from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from backend.apps.reservations.models import (
    Rental,
    RentalStatus,
)

DONEM_LABELS = {
    "AKTIF": "Aktif",
    "GELECEK": "Gelecek",
    "GECMIS": "Geçmiş",
    "IPTAL": "İptal",
}


def rental_donem_kodu(rental: Rental, *, now=None) -> str:
    """Rezervasyonu aktif / gelecek / geçmiş olarak sınıflandır."""
    now = now or timezone.now()
    if rental.status == RentalStatus.CANCELLED:
        return "IPTAL"
    if rental.status == RentalStatus.COMPLETED:
        return "GECMIS"
    if rental.status == RentalStatus.ACTIVE:
        if rental.started_at > now:
            return "GELECEK"
        return "AKTIF"
    return "GECMIS"


class RentalReturnSerializer(serializers.Serializer):
    actual_return_at = serializers.DateTimeField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    preview = serializers.BooleanField(required=False, default=False)


class RentalExtendSerializer(serializers.Serializer):
    new_ended_at = serializers.DateTimeField()


class RentalCreateSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField()
    vehicle_id = serializers.IntegerField()
    pickup_date = serializers.DateField(help_text="Alış tarihi (YYYY-MM-DD)")
    dropoff_date = serializers.DateField(help_text="Bırakış tarihi (YYYY-MM-DD)")
    daily_rate = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    deposit_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )

    def validate(self, attrs):
        if attrs["dropoff_date"] <= attrs["pickup_date"]:
            raise serializers.ValidationError(
                {"dropoff_date": "Bırakış tarihi alış tarihinden sonra olmalıdır."}
            )
        return attrs


class RentalSerializer(serializers.ModelSerializer):
    plaka = serializers.CharField(source="vehicle.plate_number", read_only=True)
    marka_model = serializers.SerializerMethodField()
    surucu_adi = serializers.CharField(source="driver.full_name", read_only=True)
    durum_label = serializers.CharField(source="get_status_display", read_only=True)
    donem_kodu = serializers.SerializerMethodField()
    donem_label = serializers.SerializerMethodField()

    class Meta:
        model = Rental
        fields = (
            "id",
            "driver_id",
            "vehicle_id",
            "surucu_adi",
            "plaka",
            "marka_model",
            "status",
            "durum_label",
            "donem_kodu",
            "donem_label",
            "started_at",
            "ended_at",
            "original_ended_at",
            "start_km",
            "end_km",
            "quoted_total",
            "daily_rate",
            "deposit_amount",
            "actual_return_at",
            "return_status",
            "price_difference",
            "created_at",
        )
        read_only_fields = fields

    def get_marka_model(self, obj: Rental) -> str:
        v = obj.vehicle
        return f"{v.brand} {v.model}"

    def get_donem_kodu(self, obj: Rental) -> str:
        return rental_donem_kodu(obj)

    def get_donem_label(self, obj: Rental) -> str:
        return DONEM_LABELS.get(rental_donem_kodu(obj), "—")