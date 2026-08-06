"""Fleet vehicle models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.companies.models import Company, CustomUser
from backend.apps.vehicles.choices import (
    BodyType,
    FuelType,
    Transmission,
    VehicleCondition,
    VehicleStatus,
)

__all__ = [
    "BodyType",
    "FuelType",
    "Transmission",
    "Vehicle",
    "VehicleCondition",
    "VehicleDocument",
    "VehicleLiveState",
    "VehicleRegistrationDetail",
    "VehicleStatus",
]


class Vehicle(models.Model):
    """A physical vehicle belonging to a company's fleet."""

    plate_number = models.CharField(
        _("plate number"),
        max_length=16,
        help_text=_("License plate; unique within the company."),
    )
    brand = models.CharField(_("brand"), max_length=64)
    model = models.CharField(_("model"), max_length=64)
    sipp_code = models.CharField(
        _("SIPP code"),
        max_length=4,
        blank=True,
        default="",
        db_index=True,
        help_text=_("ACRISS/SIPP 4 harfli kiralama sınıf kodu (ör. ECMR)."),
    )
    production_year = models.PositiveSmallIntegerField(_("production year"))
    current_km = models.PositiveIntegerField(
        _("current km"),
        default=0,
        help_text=_("Latest odometer reading in kilometers."),
    )
    status = models.CharField(
        _("status"),
        max_length=16,
        choices=VehicleStatus.choices,
        default=VehicleStatus.AVAILABLE,
        db_index=True,
    )

    # --- Genişletilmiş araç künyesi (opsiyonel; geriye dönük uyumlu) ------
    package = models.CharField(_("package"), max_length=64, blank=True, default="")
    fuel_type = models.CharField(
        _("fuel type"),
        max_length=16,
        choices=FuelType.choices,
        blank=True,
        default="",
    )
    transmission = models.CharField(
        _("transmission"),
        max_length=16,
        choices=Transmission.choices,
        blank=True,
        default="",
    )
    engine_displacement_cc = models.PositiveIntegerField(
        _("engine displacement (cc)"), null=True, blank=True
    )
    engine_power_hp = models.PositiveIntegerField(
        _("engine power (hp)"), null=True, blank=True
    )
    segment = models.CharField(
        _("segment"),
        max_length=32,
        blank=True,
        default="",
        help_text=_("Ticari segment etiketi (ör. B, C, SUV)."),
    )
    body_type = models.CharField(
        _("body type"),
        max_length=16,
        choices=BodyType.choices,
        blank=True,
        default="",
    )
    color = models.CharField(_("color"), max_length=32, blank=True, default="")
    chassis_number = models.CharField(
        _("chassis number"), max_length=32, blank=True, default=""
    )
    registration_number = models.CharField(
        _("registration number"), max_length=32, blank=True, default=""
    )
    branch_name = models.CharField(
        _("branch"), max_length=128, blank=True, default="",
        help_text=_("Aracın bağlı olduğu şube/lokasyon."),
    )
    purchase_invoice_date = models.DateField(
        _("purchase invoice date"),
        null=True,
        blank=True,
        help_text=_("Satın alma faturasının kesildiği tarih."),
    )

    # --- TCO (Toplam Sahiplik Maliyeti) — optimum satış & maliyet analizi ------
    fleet_entry_date = models.DateField(
        _("fleet entry date"),
        null=True,
        blank=True,
        help_text=_(
            "Aracın filoya fiilen giriş tarihi (kiraya hazır olduğu tarih). "
            "Gerçek maliyet hesaplarının zaman ekseni buradan başlar."
        ),
    )
    purchase_price = models.DecimalField(
        _("purchase price"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Aracın şirkete giriş / satın alım fiyatı (TL)."),
    )
    initial_industrial_expense = models.DecimalField(
        _("initial industrial expense"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text=_("Kiraya hazırlık: sanayi, aksesuar, detay vb. (TL)."),
    )
    annual_kasko_cost = models.DecimalField(
        _("annual kasko cost"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Yıllık kasko primi (TL)."),
    )
    annual_traffic_insurance_cost = models.DecimalField(
        _("annual traffic insurance cost"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Yıllık zorunlu trafik sigortası (TL)."),
    )
    annual_insurance_cost = models.DecimalField(
        _("annual insurance cost"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Yıllık kasko + trafik toplamı (ayrı alanlar boşsa kullanılır)."),
    )
    annual_mtv_cost = models.DecimalField(
        _("annual MTV cost"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Yıllık Motorlu Taşıtlar Vergisi (TL)."),
    )
    estimated_monthly_maintenance = models.DecimalField(
        _("estimated monthly maintenance"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Aylık öngörülen periyodik bakım ve lastik maliyeti (TL)."),
    )
    annual_inspection_cost = models.DecimalField(
        _("annual inspection cost"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Yıllık muayene, egzoz ve periyodik kontrol maliyeti (TL)."),
    )
    fuel_tank_capacity_liters = models.DecimalField(
        _("fuel tank capacity liters"),
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
        help_text=_("Yakıt deposu kapasitesi (litre); güncel pompa fiyatıyla günlük maliyete yansır."),
    )
    target_monthly_km = models.PositiveIntegerField(
        _("target monthly km"),
        null=True,
        blank=True,
        default=4000,
        help_text=_("Ayda beklenen ortalama kilometre."),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="vehicles",
        verbose_name=_("company"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_vehicle"
        verbose_name = _("vehicle")
        verbose_name_plural = _("vehicles")
        ordering = ("plate_number",)
        indexes = (
            models.Index(fields=("company", "status")),
            models.Index(fields=("plate_number",)),
        )
        constraints = (
            models.UniqueConstraint(
                fields=("company", "plate_number"),
                name="uniq_vehicle_plate_per_company",
            ),
        )

    def __str__(self) -> str:
        return f"{self.plate_number} — {self.brand} {self.model}"


class VehicleRegistrationDetail(models.Model):
    """FYS ruhsat/katalog tipi araç ekleme sihirbazının ek alanları.

    ``Vehicle`` ile bire-bir ilişkilidir. Bu alanların büyük çoğunluğu
    resmi ruhsat belgesini birebir yansıtan, arşiv/uyum amaçlı veri
    girişidir — maliyet/gelir hesaplama motoruyla (§3) hiçbir ilişkisi
    yoktur, o yüzden fiziksel araç künyesinden (``Vehicle``) ayrı bir
    side-table'da tutulur (``VehicleFinancialProfile`` ile aynı desen).
    Tüm alanlar opsiyoneldir — ruhsat verisi aşamalı girilebilir.
    """

    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="registration_detail",
        verbose_name=_("vehicle"),
    )

    # --- Genel Bilgiler (katalog) ---------------------------------------
    catalog_production_year_start = models.PositiveSmallIntegerField(
        _("catalog production year start"), null=True, blank=True,
        help_text=_("Modelin üretime başladığı yıl (araç kataloğu, bu aracın kendi model yılı değil)."),
    )
    catalog_production_year_end = models.PositiveSmallIntegerField(
        _("catalog production year end"), null=True, blank=True
    )
    list_price = models.DecimalField(
        _("list price"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    tafim_price = models.DecimalField(
        _("tafim price"), max_digits=12, decimal_places=2, null=True, blank=True
    )

    # --- Araç Bilgileri (ek) ---------------------------------------------
    dressing_info = models.CharField(_("dressing/livery"), max_length=255, blank=True, default="")
    extra_equipment_notes = models.TextField(_("extra equipment notes"), blank=True, default="")

    # --- Fatura Bilgileri (tarih zaten Vehicle.purchase_invoice_date) ----
    invoice_number = models.CharField(_("invoice number"), max_length=64, blank=True, default="")
    invoice_amount = models.DecimalField(
        _("invoice amount"), max_digits=12, decimal_places=2, null=True, blank=True
    )

    # --- Muayene/TÜV Bilgileri ---------------------------------------------
    inspection_valid_until = models.DateField(_("inspection valid until"), null=True, blank=True)

    # --- Ruhsat Bilgileri (resmi belge alanları) --------------------------
    registration_serial_no = models.CharField(_("registration serial no"), max_length=32, blank=True, default="")
    registration_province = models.CharField(_("registration province (İl)"), max_length=64, blank=True, default="")
    registration_district = models.CharField(_("registration district (İlçe)"), max_length=64, blank=True, default="")
    first_registration_date = models.DateField(_("first registration date (B)"), null=True, blank=True)
    registration_sequence_no = models.CharField(_("registration sequence no (Y.2)"), max_length=32, blank=True, default="")
    registration_date = models.DateField(_("registration date (I)"), null=True, blank=True)
    vehicle_type_code = models.CharField(_("vehicle type code (D.2)"), max_length=32, blank=True, default="")
    vehicle_class = models.CharField(_("vehicle class (J)"), max_length=16, blank=True, default="")
    vehicle_kind = models.CharField(_("vehicle kind (D.5)"), max_length=64, blank=True, default="")
    engine_serial_number = models.CharField(_("engine serial number (P.5)"), max_length=64, blank=True, default="")
    net_weight_kg = models.PositiveIntegerField(_("net weight kg (G.1)"), null=True, blank=True)
    max_loaded_weight_kg = models.PositiveIntegerField(_("max loaded weight kg (F.1)"), null=True, blank=True)
    train_weight_kg = models.PositiveIntegerField(_("train weight kg (G)"), null=True, blank=True)
    trailer_max_weight_kg = models.PositiveIntegerField(_("trailer max weight kg (G.2)"), null=True, blank=True)
    seat_count = models.PositiveSmallIntegerField(_("seat count (S.1)"), null=True, blank=True)
    standing_passenger_count = models.PositiveSmallIntegerField(_("standing passenger count (S.2)"), null=True, blank=True)
    power_to_weight_ratio = models.DecimalField(
        _("power to weight ratio (Q)"), max_digits=6, decimal_places=3, null=True, blank=True,
        help_text=_("kw/kg — genellikle motosiklet için, otomobillerde boş bırakılabilir."),
    )
    usage_purpose = models.CharField(_("usage purpose (Y.3)"), max_length=128, blank=True, default="")
    type_approval_no = models.CharField(_("type approval no (K)"), max_length=64, blank=True, default="")
    owner_tc_or_tax_no = models.CharField(_("owner TC/tax no (Y.4)"), max_length=16, blank=True, default="")
    owner_surname_or_title = models.CharField(_("owner surname/title (C.1.1)"), max_length=128, blank=True, default="")
    owner_first_name = models.CharField(_("owner first name (C.1.2)"), max_length=128, blank=True, default="")
    owner_address = models.TextField(_("owner address (C.1.3)"), blank=True, default="")
    rights_holders_note = models.TextField(_("rights holders note (Z.1)"), blank=True, default="")
    other_notes = models.TextField(_("other notes (Z.2)"), blank=True, default="")

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_vehicleregistrationdetail"
        verbose_name = _("vehicle registration detail")
        verbose_name_plural = _("vehicle registration details")

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} — ruhsat bilgileri"


class VehicleLiveState(models.Model):
    """Durable, cross-process snapshot of a vehicle's *latest* live telemetry.

    The live simulator (``run_simulator`` management command) and the web
    server run in separate processes and cannot share in-memory state, while
    ClickHouse may be offline locally. This relational snapshot is the
    project's "safe log mechanism": it always holds the most recent position
    for the live-stream endpoint regardless of ClickHouse availability. Full
    history still streams into ClickHouse for analytics.
    """

    # Ankara city center — sensible default before a vehicle's first ping.
    DEFAULT_LATITUDE = 39.9334
    DEFAULT_LONGITUDE = 32.8597

    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="live_state",
        verbose_name=_("vehicle"),
    )
    latitude = models.FloatField(_("latitude"), default=DEFAULT_LATITUDE)
    longitude = models.FloatField(_("longitude"), default=DEFAULT_LONGITUDE)
    speed = models.FloatField(_("speed"), default=0.0)
    fuel_level = models.FloatField(_("fuel level"), default=100.0)
    event_type = models.CharField(_("event type"), max_length=32, default="normal")
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        db_table = "api_vehiclelivestate"
        verbose_name = _("vehicle live state")
        verbose_name_plural = _("vehicle live states")

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} @ ({self.latitude:.5f}, {self.longitude:.5f})"


def vehicle_document_upload_path(instance: VehicleDocument, filename: str) -> str:
    return f"vehicle_documents/{instance.vehicle_id}/{filename}"


class VehicleDocument(models.Model):
    """Bir araca eklenmiş serbest dosya/ek (ruhsat fotokopisi, poliçe PDF'i,
    ekspertiz raporu vb.) — "Dosyalar ve Ekler" adımından/sekmesinden
    yüklenir. Kategorize edilmiş bir belge tipi yok, tek genel bir liste."""

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("vehicle"),
    )
    file = models.FileField(_("file"), upload_to=vehicle_document_upload_path)
    original_filename = models.CharField(_("original filename"), max_length=255)
    label = models.CharField(_("label"), max_length=255, blank=True, default="")
    content_type = models.CharField(_("content type"), max_length=100, blank=True, default="")
    size = models.PositiveIntegerField(_("size (bytes)"), default=0)
    uploaded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("uploaded by"),
    )
    uploaded_at = models.DateTimeField(_("uploaded at"), auto_now_add=True)

    class Meta:
        db_table = "api_vehicledocument"
        ordering = ["-uploaded_at"]
        verbose_name = _("vehicle document")
        verbose_name_plural = _("vehicle documents")

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} — {self.original_filename}"

