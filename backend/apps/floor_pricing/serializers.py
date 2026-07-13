"""Finansal modül serializer'ları."""

from __future__ import annotations

from rest_framework import serializers

from backend.apps.floor_pricing.models import (
    ExpenseCategory,
    RentalIncome,
    VehicleExpense,
    VehicleFinancialProfile,
)



class VehicleFinancialProfileSerializer(serializers.ModelSerializer):
    """Aracın satın alma + fiyat + beklenen kullanım profili (yazılabilir)."""

    class Meta:
        model = VehicleFinancialProfile
        fields = (
            "id",
            "purchase_date",
            "purchase_price",
            "seller_name",
            "condition",
            "purchase_km",
            "inspection_result",
            "notes",
            "min_daily_price",
            "target_daily_price",
            "max_daily_price",
            "delivery_location",
            "daily_km_limit",
            "monthly_km_limit",
            "planned_years_in_fleet",
            "expected_sale_date",
            "expected_sale_km",
            "expected_sale_price",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class VehicleExpenseSerializer(serializers.ModelSerializer):
    """Araç gideri (tek seferlik / tekrarlayan) — yazılabilir."""

    label = serializers.CharField(read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    recurrence_display = serializers.CharField(
        source="get_recurrence_display", read_only=True
    )

    class Meta:
        model = VehicleExpense
        fields = (
            "id",
            "vehicle",
            "category",
            "category_display",
            "custom_label",
            "label",
            "amount",
            "expense_date",
            "odometer_km",
            "recurrence",
            "recurrence_display",
            "interval_months",
            "interval_km",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "vehicle", "created_at", "updated_at")


class RentalIncomeSerializer(serializers.ModelSerializer):
    """Araç bazlı kiralama geliri — yazılabilir; toplamlar türetilir."""

    total_days = serializers.IntegerField(read_only=True)
    total_income = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = RentalIncome
        fields = (
            "id",
            "vehicle",
            "rental",
            "start_date",
            "end_date",
            "base_amount",
            "discount",
            "extra_services",
            "late_fee",
            "fuel_difference",
            "extra_km_charge",
            "total_days",
            "total_income",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "vehicle", "created_at", "updated_at")

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": "Bitiş tarihi başlangıçtan önce olamaz."}
            )
        return attrs


def expense_category_choices() -> list[dict[str, str]]:
    """Frontend için gider kategorileri (değer + etiket)."""
    return [{"value": value, "label": label} for value, label in ExpenseCategory.choices]