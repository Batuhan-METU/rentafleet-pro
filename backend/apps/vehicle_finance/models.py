"""Finansal karar destek modelleri — satın alma, gider, gelir.

Bir araç kiralama şirketinin araç başına gerçek kârını modellemek için:
  * VehicleFinancialProfile — satın alma + kiralama fiyat yapısı + beklenen kullanım
  * VehicleExpense           — tek seferlik veya tekrarlayan giderler
  * RentalIncome             — araç bazlı kiralama gelirleri
Tüm parasal alanlar DecimalField'tir; hesaplamalar servis katmanında yapılır.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.companies.models import Company
from backend.apps.rentals.models import Rental
from backend.apps.vehicle_finance.choices import (
    ExpenseCategory,
    ExpenseRecurrence,
    FinancingType,
    InsurancePolicyType,
)
from backend.apps.vehicles.models import Vehicle, VehicleCondition

__all__ = [
    "CompanyOverheadExpense",
    "CostCalculationSettings",
    "ExpenseCategory",
    "ExpenseRecurrence",
    "FinancingType",
    "InsurancePolicy",
    "InsurancePolicyType",
    "Loan",
    "LoanInstallment",
    "LoanVehicleAllocation",
    "RentalIncome",
    "VehicleExpense",
    "VehicleFinancialProfile",
]


class VehicleFinancialProfile(models.Model):
    """Bir aracın yatırım planı: satın alma, kiralama fiyatı ve çıkış stratejisi.

    ``Vehicle`` ile bire-bir ilişkilidir. Fiziksel araç künyesi ``Vehicle``da,
    parasal/plan verisi burada tutulur. Böylece OLTP çekirdeği yalın kalır.
    """

    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="financial_profile",
        verbose_name=_("vehicle"),
    )

    # --- Satın alma bilgileri ------------------------------------------
    purchase_date = models.DateField(_("purchase date"))
    purchase_price = models.DecimalField(
        _("purchase price"), max_digits=12, decimal_places=2
    )
    seller_name = models.CharField(_("seller name"), max_length=128, blank=True, default="")
    condition = models.CharField(
        _("condition"),
        max_length=8,
        choices=VehicleCondition.choices,
        default=VehicleCondition.NEW,
    )
    purchase_km = models.PositiveIntegerField(_("purchase km"), default=0)
    inspection_result = models.CharField(
        _("inspection result"), max_length=255, blank=True, default=""
    )
    notes = models.TextField(_("notes"), blank=True, default="")

    # --- Finansman (gerçek maliyet hesabı — MALIYET_HESAPLAMA_METODOLOJISI §3.1/§3.2) --
    financing_type = models.CharField(
        _("financing type"),
        max_length=8,
        choices=FinancingType.choices,
        default=FinancingType.CASH,
        help_text=_(
            "Aracın satın alımı nasıl finanse edildi. CASH: tamamı nakit/özkaynak. "
            "LOAN: tamamı kredili (bkz. LoanVehicleAllocation). MIXED: kısmen kredi, "
            "kısmen nakit — nakit kısmı cash_financed_amount alanındadır."
        ),
    )
    cash_financed_amount = models.DecimalField(
        _("cash financed amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Nakit/özkaynak ile finanse edilen tutar (TL). CASH'te purchase_price'a "
            "eşit kabul edilir, LOAN'da 0/boş, MIXED'te aracın kredi dışı kalan kısmı. "
            "Nakit fırsat maliyeti hesabının (§3.2) tek girdisidir."
        ),
    )

    # --- Kiralama fiyat yapısı -----------------------------------------
    min_daily_price = models.DecimalField(
        _("minimum daily price"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    target_daily_price = models.DecimalField(
        _("target daily price"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    max_daily_price = models.DecimalField(
        _("maximum daily price"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    delivery_location = models.CharField(
        _("delivery location"), max_length=128, blank=True, default=""
    )
    daily_km_limit = models.PositiveIntegerField(_("daily km limit"), null=True, blank=True)
    monthly_km_limit = models.PositiveIntegerField(_("monthly km limit"), null=True, blank=True)

    # --- Beklenen kullanım / çıkış -------------------------------------
    planned_years_in_fleet = models.DecimalField(
        _("planned years in fleet"),
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text=_("Aracın filoda kalması planlanan yıl (ör. 2.5)."),
    )
    expected_sale_date = models.DateField(_("expected sale date"), null=True, blank=True)
    expected_sale_km = models.PositiveIntegerField(
        _("expected sale km"), null=True, blank=True
    )
    expected_sale_price = models.DecimalField(
        _("expected sale price"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Boş ise sistem amortisman eğrisinden tahmin eder."),
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_vehiclefinancialprofile"
        verbose_name = _("vehicle financial profile")
        verbose_name_plural = _("vehicle financial profiles")

    def __str__(self) -> str:
        return f"Finans profili — {self.vehicle.plate_number}"


class VehicleExpense(models.Model):
    """Bir araca ait tek seferlik veya tekrarlayan gider kaydı.

    Tekrarlayan giderlerde (kasko yılda 1, bakım 15.000 km'de bir) periyot
    ``recurrence`` + ``interval_months`` / ``interval_km`` ile modellenir; ileriye
    dönük projeksiyon servis katmanında yapılır.
    """

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name=_("vehicle"),
    )
    category = models.CharField(
        _("category"),
        max_length=32,
        choices=ExpenseCategory.choices,
        default=ExpenseCategory.OTHER,
        db_index=True,
    )
    custom_label = models.CharField(
        _("custom label"),
        max_length=128,
        blank=True,
        default="",
        help_text=_("'Diğer' kategorisi için serbest açıklama."),
    )
    amount = models.DecimalField(_("amount"), max_digits=12, decimal_places=2)
    income_amount = models.DecimalField(
        _("income amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_(
            "Bu gidere bağlı geri kazanım/tahsilat (ör. sigorta tazminatı, "
            "müşteriye yansıtılan hasar bedeli) — opsiyonel."
        ),
    )
    income_source = models.CharField(
        _("income source"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Gelirin nereden geldiği (ör. 'Sigorta Tazminatı', 'Müşteri Tahsilatı')."),
    )
    expense_date = models.DateField(_("expense date"), db_index=True)
    odometer_km = models.PositiveIntegerField(
        _("odometer km"),
        null=True,
        blank=True,
        help_text=_("Giderin yapıldığı andaki kilometre (km bazlı projeksiyon için)."),
    )
    recurrence = models.CharField(
        _("recurrence"),
        max_length=16,
        choices=ExpenseRecurrence.choices,
        default=ExpenseRecurrence.ONE_TIME,
        db_index=True,
    )
    interval_months = models.PositiveSmallIntegerField(
        _("interval (months)"),
        null=True,
        blank=True,
        help_text=_("Zaman bazlı tekrar için periyot (ör. Kasko=12)."),
    )
    interval_km = models.PositiveIntegerField(
        _("interval (km)"),
        null=True,
        blank=True,
        help_text=_("Kilometre bazlı tekrar için periyot (ör. Bakım=15000)."),
    )
    notes = models.TextField(_("notes"), blank=True, default="")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_vehicleexpense"
        verbose_name = _("vehicle expense")
        verbose_name_plural = _("vehicle expenses")
        ordering = ("-expense_date", "-created_at")
        indexes = (
            models.Index(fields=("vehicle", "category")),
            models.Index(fields=("vehicle", "recurrence")),
        )

    @property
    def label(self) -> str:
        if self.category == ExpenseCategory.OTHER and self.custom_label:
            return self.custom_label
        return self.get_category_display()

    def __str__(self) -> str:
        return f"{self.label}: {self.amount} TL → {self.vehicle.plate_number}"


class RentalIncome(models.Model):
    """Araç bazlı kiralama geliri kaydı.

    Telemetri ağırlıklı ``Rental`` modelinden bağımsız tutulur; böylece gelir
    kaydı, tam bir kiralama dönemi (sürücü/telemetri) olmadan da girilebilir.
    İsteğe bağlı olarak bir ``Rental``a bağlanabilir.
    """

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="incomes",
        verbose_name=_("vehicle"),
    )
    rental = models.ForeignKey(
        Rental,
        on_delete=models.SET_NULL,
        related_name="income_records",
        verbose_name=_("rental"),
        null=True,
        blank=True,
    )
    start_date = models.DateField(_("start date"), db_index=True)
    end_date = models.DateField(_("end date"))
    base_amount = models.DecimalField(
        _("base amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Günlük ücret × gün (indirim öncesi taban tutar)."),
    )
    discount = models.DecimalField(
        _("discount"), max_digits=12, decimal_places=2, default=0
    )
    extra_services = models.DecimalField(
        _("extra services"), max_digits=12, decimal_places=2, default=0
    )
    late_fee = models.DecimalField(
        _("late fee"), max_digits=12, decimal_places=2, default=0
    )
    fuel_difference = models.DecimalField(
        _("fuel difference"), max_digits=12, decimal_places=2, default=0
    )
    extra_km_charge = models.DecimalField(
        _("extra km charge"), max_digits=12, decimal_places=2, default=0
    )
    notes = models.TextField(_("notes"), blank=True, default="")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_rentalincome"
        verbose_name = _("rental income")
        verbose_name_plural = _("rental incomes")
        ordering = ("-start_date", "-created_at")
        indexes = (
            models.Index(fields=("vehicle", "start_date")),
        )

    @property
    def total_days(self) -> int:
        return max((self.end_date - self.start_date).days, 1)

    @property
    def total_income(self):
        """İndirim düşülmüş, ek kalemler eklenmiş toplam gelir."""
        return (
            self.base_amount
            - self.discount
            + self.extra_services
            + self.late_fee
            + self.fuel_difference
            + self.extra_km_charge
        )

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number}: {self.total_income} TL ({self.start_date}→{self.end_date})"


# ======================================================================
# GERÇEK MALİYET HESABI MODELLERİ — MALIYET_HESAPLAMA_METODOLOJISI §3
# ----------------------------------------------------------------------
# Kredi (§3.1), nakit fırsat maliyeti (§3.2, VehicleFinancialProfile'daki
# financing_type/cash_financed_amount üzerinden), genel gider (§3.3),
# sigorta (§3.4) için gerçek/senaryo verisi bu modellerde tutulur.
# Operasyon gideri (§3.5) zaten yukarıdaki VehicleExpense'tir, yeni model
# gerekmez. Hesaplama mantığının tamamı servis katmanındadır
# (backend/infrastructure/services/cost_calculation/); bu modeller sadece
# kaynak veriyi tutar.
# ======================================================================


class Loan(models.Model):
    """Bir veya daha fazla aracı finanse eden kredi (§3.1).

    Bir kredi birden fazla aracı finanse edebilir; hangi aracın ne kadarını
    finanse ettiği ``LoanVehicleAllocation`` ile ayrıca tutulur. Taksit
    planı (``LoanInstallment``) bu kredinin parametrelerinden azalan
    bakiyeli amortisman formülüyle üretilip precompute edilir — kredi
    parametreleri değişirse yeniden üretilmesi gerekir.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="loans",
        verbose_name=_("company"),
    )
    loan_no = models.CharField(
        _("loan reference no"),
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text=_("Kaynak banka/sistem kredi kimliği (ör. \"BURGAN-55.000.000\")."),
    )
    lender_name = models.CharField(
        _("lender name"), max_length=128, blank=True, default=""
    )
    principal_amount = models.DecimalField(
        _("principal amount"),
        max_digits=14,
        decimal_places=2,
        help_text=_("Kredi anaparası (P)."),
    )
    monthly_interest_rate = models.DecimalField(
        _("monthly interest rate"),
        max_digits=7,
        decimal_places=5,
        help_text=_("Aylık faiz oranı (r) — ör. 0.03500 = %3,5."),
    )
    term_months = models.PositiveSmallIntegerField(
        _("term (months)"), help_text=_("Kredi vadesi ay cinsinden (n).")
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"), null=True, blank=True)
    bsmv_rate = models.DecimalField(
        _("BSMV rate"),
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_(
            "Boş bırakılırsa CostCalculationSettings.bsmv_rate kullanılır."
        ),
    )
    notes = models.TextField(_("notes"), blank=True, default="")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_loan"
        verbose_name = _("loan")
        verbose_name_plural = _("loans")
        ordering = ("-start_date",)

    def __str__(self) -> str:
        return f"{self.lender_name or 'Kredi'} — {self.principal_amount} TL ({self.term_months} ay)"


class LoanVehicleAllocation(models.Model):
    """Bir kredinin bir aracı finanse eden kısmı (§3.1 Adım 2).

    ``financed_amount`` aracın TAM fiyatı DEĞİLDİR — sadece bu krediyle
    finanse edilen paydır. Karma finansmanlı bir araç, kendi payından
    fazla kredi maliyeti yüklenmemelidir.
    """

    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="vehicle_allocations",
        verbose_name=_("loan"),
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="loan_allocations",
        verbose_name=_("vehicle"),
    )
    financed_amount = models.DecimalField(
        _("financed amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Bu krediyle finanse edilen tutar (aracın tam fiyatı değil)."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        db_table = "api_loanvehicleallocation"
        verbose_name = _("loan vehicle allocation")
        verbose_name_plural = _("loan vehicle allocations")
        ordering = ("id",)
        constraints = (
            models.UniqueConstraint(
                fields=("loan", "vehicle"),
                name="uniq_loan_vehicle_allocation",
            ),
        )
        indexes = (models.Index(fields=("vehicle",)),)

    def __str__(self) -> str:
        return f"{self.loan_id} → {self.vehicle.plate_number}: {self.financed_amount} TL"


class LoanInstallment(models.Model):
    """Bir kredinin azalan bakiyeli amortisman tablosundaki tek taksit satırı.

    ``generate_amortization_schedule`` (cost_calculation servis katmanı)
    tarafından üretilip precompute edilir; her adımın çıktısı ayrı
    denetlenebilir olsun diye DB'de saklanır (bkz. dokümanın §3.1'deki
    "her adımın çıktısı ayrıca incelenebilir" ilkesi).
    """

    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="installments",
        verbose_name=_("loan"),
    )
    installment_no = models.PositiveSmallIntegerField(_("installment number"))
    due_date = models.DateField(_("due date"), db_index=True)
    total_amount = models.DecimalField(_("total amount"), max_digits=12, decimal_places=2)
    principal_amount = models.DecimalField(
        _("principal amount"), max_digits=12, decimal_places=2
    )
    interest_amount = models.DecimalField(
        _("interest amount"), max_digits=12, decimal_places=2
    )
    bsmv_amount = models.DecimalField(_("BSMV amount"), max_digits=12, decimal_places=2)
    remaining_principal_after = models.DecimalField(
        _("remaining principal after"), max_digits=14, decimal_places=2
    )

    class Meta:
        db_table = "api_loaninstallment"
        verbose_name = _("loan installment")
        verbose_name_plural = _("loan installments")
        ordering = ("loan", "installment_no")
        constraints = (
            models.UniqueConstraint(
                fields=("loan", "installment_no"),
                name="uniq_loan_installment_no",
            ),
        )
        indexes = (models.Index(fields=("loan", "due_date")),)

    def __str__(self) -> str:
        return f"{self.loan_id} taksit #{self.installment_no} — {self.due_date}"


class InsurancePolicy(models.Model):
    """Bir araca ait, tarihli sigorta/kasko poliçesi (§3.4).

    Havuzlu dağıtım YOKTUR — her poliçe tek bir araca aittir, tipik olarak
    1 yıllık ve tek seferde peşin ödenmiş kabul edilir. Bir araç birden
    fazla poliçe TİPİNE (Trafik + Kasko + Yeşil Kart) sahip olabilir.
    """

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="insurance_policies",
        verbose_name=_("vehicle"),
    )
    policy_type = models.CharField(
        _("policy type"),
        max_length=16,
        choices=InsurancePolicyType.choices,
        db_index=True,
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Poliçenin tek seferde ödenen toplam tutarı (TL)."),
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    policy_number = models.CharField(
        _("policy number"), max_length=64, blank=True, default=""
    )
    notes = models.TextField(_("notes"), blank=True, default="")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_insurancepolicy"
        verbose_name = _("insurance policy")
        verbose_name_plural = _("insurance policies")
        ordering = ("-start_date",)
        indexes = (models.Index(fields=("vehicle", "policy_type")),)

    def __str__(self) -> str:
        return (
            f"{self.get_policy_type_display()}: {self.amount} TL → "
            f"{self.vehicle.plate_number} ({self.start_date}→{self.end_date})"
        )


class CompanyOverheadExpense(models.Model):
    """Şirketin araca özel OLMAYAN genel gideri, günlük granularitede (§3.3).

    Personel, kira, elektrik vb. — filodaki tüm araçlara fiyat ağırlıklı
    olarak günlük bazda dağıtılır (bkz. overhead_allocation_service).
    ``category`` alanı sadece raporlama amaçlıdır; havuz TEKTİR, kategoriye
    göre ayrı dağıtım yapılmaz.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="overhead_expenses",
        verbose_name=_("company"),
    )
    expense_date = models.DateField(_("expense date"), db_index=True)
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("O güne ait toplam genel gider (TL)."),
    )
    category = models.CharField(
        _("category"),
        max_length=64,
        blank=True,
        default="",
        help_text=_("Sadece raporlama amaçlı (ör. Personel, Kira) — hesaba etkisi yok."),
    )
    source_note = models.CharField(
        _("source note"),
        max_length=128,
        blank=True,
        default="",
        help_text=_("Verinin geldiği kaynak/import kaydı (ör. '2026-03 muhasebe importu')."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_companyoverheadexpense"
        verbose_name = _("company overhead expense")
        verbose_name_plural = _("company overhead expenses")
        ordering = ("-expense_date",)
        constraints = (
            models.UniqueConstraint(
                fields=("company", "expense_date", "category"),
                name="uniq_overhead_company_date_category",
            ),
        )
        indexes = (models.Index(fields=("company", "expense_date")),)

    def __str__(self) -> str:
        return f"{self.company_id} @ {self.expense_date}: {self.amount} TL"


class CostCalculationSettings(models.Model):
    """Şirket bazlı gerçek maliyet hesabı parametreleri.

    Doküman bu oranların ("%40 mevduat faizi", "%5 BSMV", "%20 hedef kâr")
    iş kararı/güncel piyasa oranı olduğunu ve güncellenmesi gerektiğini
    vurgular (§3.2, §6) — bu yüzden kod seviyesinde sabit değil, kiracı
    şirket başına değiştirilebilir bir DB kaydıdır.
    """

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="cost_calculation_settings",
        verbose_name=_("company"),
    )
    annual_deposit_rate = models.DecimalField(
        _("annual deposit rate"),
        max_digits=6,
        decimal_places=4,
        default=Decimal("0.4000"),
        help_text=_("Nakit fırsat maliyeti için yıllık mevduat faiz oranı (§3.2)."),
    )
    bsmv_rate = models.DecimalField(
        _("BSMV rate"),
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.0500"),
        help_text=_("Kredi faizi üzerinden alınan BSMV oranı (§3.1)."),
    )
    target_profit_margin = models.DecimalField(
        _("target profit margin"),
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.2000"),
        help_text=_("Kurtaran fiyat hesabında hedef kâr marjı (§6)."),
    )
    cash_opportunity_term_months = models.PositiveIntegerField(
        _("cash opportunity term (months)"),
        default=36,
        help_text=_(
            "Nakit fırsat maliyetinin işlemeye devam ettiği varsayılan süre "
            "(§3.2) — bir kredinin vadesine paralel: bu süre filoya giriş "
            "tarihinden itibaren dolunca fırsat maliyeti durur."
        ),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_costcalculationsettings"
        verbose_name = _("cost calculation settings")
        verbose_name_plural = _("cost calculation settings")

    def __str__(self) -> str:
        return f"Maliyet ayarları — {self.company.name}"
