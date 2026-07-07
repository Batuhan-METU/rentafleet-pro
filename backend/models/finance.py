"""Financial and market pricing models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from .rental import Rental
from .vehicle import Vehicle, VehicleCondition

class CompetitorPrice(models.Model):
    """Rakip platform / firma günlük kiralama fiyatı (müdür tarafından girilir).

    Her araç için kaynak başına tek kayıt tutulur; POST ile güncellenir.
    SIPP kodu segment bazlı raporlama için denormalize edilir.
    """

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="competitor_prices",
        verbose_name=_("vehicle"),
    )
    sipp_code = models.CharField(
        _("SIPP code"),
        max_length=4,
        blank=True,
        default="",
        db_index=True,
    )
    source_name = models.CharField(
        _("source name"),
        max_length=128,
        help_text=_("Örn. Avis, Sixt, Garenta"),
    )
    provider_name = models.CharField(
        _("provider name"),
        max_length=64,
        blank=True,
        default="",
    )
    external_reference = models.CharField(
        _("external reference"),
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    daily_price = models.DecimalField(
        _("daily price"),
        max_digits=10,
        decimal_places=2,
    )
    similar_vehicle = models.CharField(
        _("similar vehicle"),
        max_length=128,
        blank=True,
        default="",
        help_text=_("Piyasada eşleştirilen benzer araç (ör. Fiat Egea)."),
    )
    pickup_date = models.DateField(
        _("pickup date"),
        db_index=True,
        help_text=_("Piyasa fiyatının geçerli olduğu kiralama başlangıç tarihi."),
    )
    dropoff_date = models.DateField(
        _("dropoff date"),
        db_index=True,
        help_text=_("Piyasa fiyatının geçerli olduğu kiralama bitiş tarihi."),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("competitor price")
        verbose_name_plural = _("competitor prices")
        ordering = ("source_name",)
        constraints = (
            models.UniqueConstraint(
                fields=("vehicle", "external_reference", "pickup_date", "dropoff_date"),
                condition=~models.Q(external_reference=""),
                name="uniq_competitor_price_vehicle_ext_ref_window",
            ),
        )
        indexes = (
            models.Index(fields=("vehicle", "sipp_code")),
            models.Index(fields=("pickup_date", "dropoff_date")),
        )

    def __str__(self) -> str:
        return f"{self.source_name}: {self.daily_price} TL → {self.vehicle.plate_number}"


class EnuygunMarketSnapshot(models.Model):
    """Enuygun API çekimi — her kiralama penceresi (alış/dönüş) için bir kayıt."""

    snapshot_date = models.DateField(_("snapshot date"), db_index=True)
    city = models.CharField(_("city"), max_length=64)
    pickup_date = models.DateField(_("pickup date"), db_index=True)
    dropoff_date = models.DateField(_("dropoff date"), db_index=True)
    fetched_at = models.DateTimeField(_("fetched at"), auto_now_add=True)
    reservation_count = models.PositiveIntegerField(_("reservation count"), default=0)

    class Meta:
        verbose_name = _("Enuygun market snapshot")
        verbose_name_plural = _("Enuygun market snapshots")
        ordering = ("-pickup_date", "-fetched_at")
        constraints = (
            models.UniqueConstraint(
                fields=("pickup_date", "dropoff_date", "city"),
                name="uniq_market_snapshot_rental_window",
            ),
        )

    def __str__(self) -> str:
        return f"{self.city} @ {self.snapshot_date} ({self.reservation_count} kayıt)"


class EnuygunCachedReservation(models.Model):
    """Enuygun'dan alınan ham rezervasyon satırı (günlük snapshot)."""

    snapshot = models.ForeignKey(
        EnuygunMarketSnapshot,
        on_delete=models.CASCADE,
        related_name="reservations",
        verbose_name=_("snapshot"),
    )
    reference_id = models.CharField(_("reference id"), max_length=64)
    provider = models.CharField(_("provider"), max_length=64)
    brand = models.CharField(_("brand"), max_length=64)
    model = models.CharField(_("model"), max_length=128)
    segment = models.CharField(_("segment"), max_length=4, blank=True, default="")
    vehicle_class = models.CharField(_("vehicle class"), max_length=64, blank=True, default="")
    fuel = models.CharField(_("fuel"), max_length=64, blank=True, default="")
    transmission = models.CharField(_("transmission"), max_length=32, blank=True, default="")
    daily_price = models.DecimalField(_("daily price"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=8, default="TRY")

    class Meta:
        verbose_name = _("cached Enuygun reservation")
        verbose_name_plural = _("cached Enuygun reservations")
        ordering = ("provider", "brand", "model")
        constraints = (
            models.UniqueConstraint(
                fields=("snapshot", "reference_id"),
                name="uniq_cached_reservation_per_snapshot",
            ),
        )
        indexes = (
            models.Index(fields=("snapshot", "segment")),
        )

    def __str__(self) -> str:
        return f"{self.provider} — {self.brand} {self.model} @ {self.daily_price} {self.currency}"

    def to_reservation_dict(self) -> dict:
        """Segment filtresi için API formatına yakın sözlük."""
        return {
            "referenceId": self.reference_id,
            "vehicle": {
                "brand": self.brand,
                "name": self.model,
                "class": self.vehicle_class,
                "fuel": self.fuel,
                "transmission": self.transmission,
                "sippCode": None,
            },
            "company": {"name": self.provider},
            "price": {
                "dailyPrice": float(self.daily_price),
                "currency": self.currency,
            },
        }


# ======================================================================
# FİNANSAL KARAR DESTEK MODELLERİ
# ----------------------------------------------------------------------
# Bir araç kiralama şirketinin araç başına gerçek kârını modellemek için:
#   * VehicleFinancialProfile — satın alma + kiralama fiyat yapısı + beklenen kullanım
#   * VehicleExpense           — tek seferlik veya tekrarlayan giderler
#   * RentalIncome             — araç bazlı kiralama gelirleri
# Tüm parasal alanlar DecimalField'tir; hesaplamalar servis katmanında yapılır.
# ======================================================================


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
        verbose_name = _("vehicle financial profile")
        verbose_name_plural = _("vehicle financial profiles")

    def __str__(self) -> str:
        return f"Finans profili — {self.vehicle.plate_number}"


class ExpenseCategory(models.TextChoices):
    """Gider türleri. Yeni tür eklemek için tek satır yeterlidir."""

    # Sigorta / vergi / resmi
    KASKO = "KASKO", _("Kasko")
    TRAFIK_SIGORTASI = "TRAFIK_SIGORTASI", _("Trafik Sigortası")
    MTV = "MTV", _("MTV")
    NOTER = "NOTER", _("Noter")
    PLAKA = "PLAKA", _("Plaka")
    RUHSAT = "RUHSAT", _("Ruhsat")
    EKSPERTIZ = "EKSPERTIZ", _("Ekspertiz")
    MUAYENE = "MUAYENE", _("Muayene")
    # Bakım / mekanik
    PERIYODIK_BAKIM = "PERIYODIK_BAKIM", _("Periyodik Bakım")
    MOTOR_BAKIM = "MOTOR_BAKIM", _("Motor Bakımı")
    YAG_DEGISIMI = "YAG_DEGISIMI", _("Yağ Değişimi")
    FILTRE = "FILTRE", _("Filtre")
    LASTIK = "LASTIK", _("Lastik Değişimi")
    BALATA = "BALATA", _("Balata")
    AKU = "AKU", _("Akü")
    SANAYI = "SANAYI", _("Sanayi Masrafı")
    # Kaporta / kozmetik
    KAPORTA = "KAPORTA", _("Kaporta")
    BOYA = "BOYA", _("Boya")
    CAM = "CAM", _("Cam Değişimi")
    FAR = "FAR", _("Far")
    DETAYLI_TEMIZLIK = "DETAYLI_TEMIZLIK", _("Detaylı Temizlik")
    SERAMIK = "SERAMIK", _("Seramik Kaplama")
    PPF = "PPF", _("PPF")
    # Aksesuar / donanım
    GPS = "GPS", _("GPS Takılması")
    ARAC_TAKIP = "ARAC_TAKIP", _("Araç Takip Sistemi")
    YEDEK_ANAHTAR = "YEDEK_ANAHTAR", _("Yedek Anahtar")
    # İşletme / operasyon
    YAKIT = "YAKIT", _("Yakıt")
    ADBLUE = "ADBLUE", _("AdBlue")
    OTOPARK = "OTOPARK", _("Otopark")
    CEKICI = "CEKICI", _("Çekici")
    CEZA = "CEZA", _("Ceza")
    HGS_OGS = "HGS_OGS", _("HGS / OGS")
    YIKAMA = "YIKAMA", _("Yıkama")
    VALE = "VALE", _("Vale")
    DIGER = "DIGER", _("Diğer")


class ExpenseRecurrence(models.TextChoices):
    """Gider tekrarlama biçimi."""

    ONE_TIME = "ONE_TIME", _("Tek Seferlik")
    TIME_BASED = "TIME_BASED", _("Zaman Bazlı")  # her N ayda bir
    KM_BASED = "KM_BASED", _("Kilometre Bazlı")  # her N km'de bir


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
        default=ExpenseCategory.DIGER,
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
        verbose_name = _("vehicle expense")
        verbose_name_plural = _("vehicle expenses")
        ordering = ("-expense_date", "-created_at")
        indexes = (
            models.Index(fields=("vehicle", "category")),
            models.Index(fields=("vehicle", "recurrence")),
        )

    @property
    def label(self) -> str:
        if self.category == ExpenseCategory.DIGER and self.custom_label:
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

