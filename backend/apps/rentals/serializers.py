"""Kiralama serializer'ları."""

from __future__ import annotations

from datetime import time

from django.utils import timezone
from rest_framework import serializers

from backend.apps.rentals.models import (
    Rental,
    RentalStatus,
)

PERIOD_LABELS = {
    "ACTIVE": "Aktif",
    "UPCOMING": "Gelecek",
    "PAST": "Geçmiş",
    "CANCELLED": "İptal",
}


def rental_period_code(rental: Rental, *, now=None) -> str:
    """Kiralamayı aktif / gelecek / geçmiş olarak sınıflandır.

    ``status`` araç fiilen "Teslim Al" ile kapatılana kadar ACTIVE kalır
    (otomatik bir iş yok) — sözleşme bitiş tarihi (``ended_at``) geçmiş
    olsa bile araç henüz teslim alınmadıysa kiralama hâlâ "Aktif"tir; bu
    durum ayrı bir kategori değil, ``rental_is_overdue`` ile bayraklanan bir
    uyarıdır (bkz. o fonksiyonun docstring'i).
    """
    now = now or timezone.now()
    if rental.status == RentalStatus.CANCELLED:
        return "CANCELLED"
    if rental.status == RentalStatus.COMPLETED:
        return "PAST"
    if rental.status == RentalStatus.ACTIVE:
        if rental.started_at > now:
            return "UPCOMING"
        return "ACTIVE"
    return "PAST"


def rental_is_overdue(rental: Rental, *, now=None) -> bool:
    """Sözleşme bitiş tarihi geçmiş ama araç henüz "Teslim Al" ile
    kapatılmamış mı? Aktif listesinde satır içi uyarı rozeti için — kiralamayı
    ayrı bir kategoriye taşımaz, sadece işaretler.
    """
    now = now or timezone.now()
    return (
        rental.status == RentalStatus.ACTIVE
        and rental.started_at <= now
        and rental.ended_at is not None
        and rental.ended_at < now
    )


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
    # Anlaşılan gerçek teslim alma/etme saati — gönderilmezse eski sabit
    # 10:00 varsayımı korunur (bkz. views.py:_datetime_at).
    pickup_time = serializers.TimeField(required=False, default=time(10, 0))
    dropoff_time = serializers.TimeField(required=False, default=time(10, 0))
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
    plate_number = serializers.CharField(source="vehicle.plate_number", read_only=True)
    brand_model = serializers.SerializerMethodField()
    driver_name = serializers.CharField(source="driver.full_name", read_only=True)
    driver_gender = serializers.CharField(source="driver.gender", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    period_code = serializers.SerializerMethodField()
    period_label = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Rental
        fields = (
            "id",
            "driver_id",
            "vehicle_id",
            "driver_name",
            "driver_gender",
            "plate_number",
            "brand_model",
            "status",
            "status_label",
            "period_code",
            "period_label",
            "is_overdue",
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

    def get_brand_model(self, obj: Rental) -> str:
        v = obj.vehicle
        return f"{v.brand} {v.model}"

    def get_period_code(self, obj: Rental) -> str:
        return rental_period_code(obj)

    def get_period_label(self, obj: Rental) -> str:
        return PERIOD_LABELS.get(rental_period_code(obj), "—")

    def get_is_overdue(self, obj: Rental) -> bool:
        return rental_is_overdue(obj)