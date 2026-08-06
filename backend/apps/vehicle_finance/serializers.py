"""Finansal modül serializer'ları."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from backend.apps.vehicle_finance.models import (
    CompanyOverheadExpense,
    ExpenseCategory,
    InsurancePolicy,
    Loan,
    LoanInstallment,
    LoanVehicleAllocation,
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
            "financing_type",
            "cash_financed_amount",
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
            "income_amount",
            "income_source",
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


class LoanSerializer(serializers.ModelSerializer):
    """Kredi tanımı (§3.1) — yazılabilir; taksit planı ayrıca üretilir."""

    class Meta:
        model = Loan
        fields = (
            "id",
            "company",
            "loan_no",
            "lender_name",
            "principal_amount",
            "monthly_interest_rate",
            "term_months",
            "start_date",
            "end_date",
            "bsmv_rate",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "company", "created_at", "updated_at")


class LoanInstallmentSerializer(serializers.ModelSerializer):
    """Bir kredinin taksit planındaki tek satır (§3.1) — salt okunur.

    Elle düzenlenmez; ``generate_amortization_schedule`` tarafından
    kredi oluşturulduğunda/güncellendiğinde üretilip DB'ye yazılır.
    """

    class Meta:
        model = LoanInstallment
        fields = (
            "id",
            "installment_no",
            "due_date",
            "total_amount",
            "principal_amount",
            "interest_amount",
            "bsmv_amount",
            "remaining_principal_after",
        )
        read_only_fields = fields


class LoanVehicleAllocationSerializer(serializers.ModelSerializer):
    """Bir kredinin bir aracı finanse eden kısmı (§3.1 Adım 2) — yazılabilir.

    ``financed_amount``'ın, aracın zaten mevcut tahsisleri + bu tahsisle
    birlikte aracın ``purchase_price``'ını aşmadığını doğrular (doc'un
    "karma finansmanlı araç kendi payından fazla kredi maliyeti
    yüklenmemeli" uyarısına paralel bütünlük kontrolü).
    """

    plate_number = serializers.CharField(source="vehicle.plate_number", read_only=True)
    brand = serializers.CharField(source="vehicle.brand", read_only=True)
    model_name = serializers.CharField(source="vehicle.model", read_only=True)
    purchase_price = serializers.DecimalField(
        source="vehicle.purchase_price", max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = LoanVehicleAllocation
        fields = (
            "id",
            "loan",
            "vehicle",
            "plate_number",
            "brand",
            "model_name",
            "purchase_price",
            "financed_amount",
            "created_at",
        )
        read_only_fields = ("id", "loan", "created_at")

    def validate(self, attrs: dict) -> dict:
        vehicle = attrs.get("vehicle") or getattr(self.instance, "vehicle", None)
        financed_amount = attrs.get("financed_amount")
        if vehicle is None or financed_amount is None:
            return attrs

        request = self.context.get("request")
        user_company_id = getattr(getattr(request, "user", None), "company_id", None)
        if user_company_id is not None and vehicle.company_id != user_company_id:
            raise serializers.ValidationError(
                {"vehicle": "Bu araç sizin şirketinize ait değil."}
            )

        purchase_price = vehicle.purchase_price
        if purchase_price is None:
            raise serializers.ValidationError(
                {"vehicle": "Bu aracın satın alım fiyatı girilmemiş; tahsis yapılamaz."}
            )

        existing_total = (
            LoanVehicleAllocation.objects.filter(vehicle=vehicle)
            # `self.instance` oluşturma sırasında None'dır (`.exclude(pk=None)`
            # Django'da hiçbir satırı hariç tutmaz, güvenli bir no-op'tur);
            # güncellemede kendi mevcut kaydını hariç tutar.
            .exclude(pk=getattr(self.instance, "pk", None))  # type: ignore[misc]
            .aggregate(total=Sum("financed_amount"))["total"]
            or Decimal("0")
        )
        if existing_total + financed_amount > purchase_price:
            raise serializers.ValidationError(
                {
                    "financed_amount": (
                        f"Bu araca ait toplam kredi tahsisi ({existing_total + financed_amount} TL) "
                        f"satın alım fiyatını ({purchase_price} TL) aşamaz."
                    )
                }
            )
        return attrs


class VehicleLoanAllocationSerializer(serializers.ModelSerializer):
    """Bir aracın kredi tahsisleri, kredinin kendi bilgileriyle birlikte (salt okunur).

    Araç detay sayfasının "Kredi Detayları" sekmesi için — mevcut
    ``LoanVehicleAllocationSerializer`` yazılabilir/loan-scope'lu akışı
    (kredi altında tahsis ekleme) bozmadan, araç tarafından bakıldığında
    krediye ait özet bilgileri de (lender, faiz oranı, vade) tek çağrıda
    döner.
    """

    loan = LoanSerializer(read_only=True)

    class Meta:
        model = LoanVehicleAllocation
        fields = ("id", "loan", "financed_amount", "created_at")


class LoanDetailSerializer(LoanSerializer):
    """Kredi detay sayfası için — taksit planı ve araç tahsisleri nested
    olarak eklenir (§ Kredi Detay Sayfası). Liste görünümü (``LoanSerializer``)
    bunları İÇERMEZ — payload'ı şişirmemek için sadece tek kredi görüntülenirken
    kullanılır (bkz. ``VehicleDetailUpdateView``'daki yalın-liste/nested-detay ayrımı).
    """

    installments = LoanInstallmentSerializer(many=True, read_only=True)
    vehicle_allocations = LoanVehicleAllocationSerializer(many=True, read_only=True)

    class Meta(LoanSerializer.Meta):
        # Kasıtlı olarak temel Meta.fields'tan daha UZUN bir tuple — DRF'in
        # yaygın "detay serializer, liste serializer'ın alanlarını genişletir"
        # deseni; mypy bunu (yanlışlıkla) Liskov ihlali sanıyor.
        fields = LoanSerializer.Meta.fields + ("installments", "vehicle_allocations")  # type: ignore[assignment]


class InsurancePolicySerializer(serializers.ModelSerializer):
    """Araç sigorta/kasko poliçesi (§3.4) — yazılabilir."""

    policy_type_display = serializers.CharField(source="get_policy_type_display", read_only=True)

    class Meta:
        model = InsurancePolicy
        fields = (
            "id",
            "vehicle",
            "policy_type",
            "policy_type_display",
            "amount",
            "start_date",
            "end_date",
            "policy_number",
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


class CompanyOverheadExpenseSerializer(serializers.ModelSerializer):
    """Şirket geneli genel gider kaydı (§3.3) — yazılabilir; manuel giriş için."""

    class Meta:
        model = CompanyOverheadExpense
        fields = (
            "id",
            "company",
            "expense_date",
            "amount",
            "category",
            "source_note",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "company", "created_at", "updated_at")


def expense_category_choices() -> list[dict[str, str]]:
    """Frontend için gider kategorileri (değer + etiket)."""
    # `label` Django'nun choices'ında lazy bir çeviri nesnesidir (_StrPromise)
    # — DRF'in Response renderer'ı bunu otomatik str'e çevirir ama bu
    # fonksiyonun imzası (list[dict[str, str]]) GERÇEK str taahhüt ediyor;
    # `str()` bu taahhüdü zorunlu kılar (ör. doğrudan json.dumps'a
    # verilseydi lazy proxy hata verirdi).
    return [{"value": value, "label": str(label)} for value, label in ExpenseCategory.choices]