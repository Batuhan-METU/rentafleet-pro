"""Fleet vehicle models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from .company import Company

class VehicleStatus(models.TextChoices):
    """Lifecycle state of a fleet vehicle."""

    AVAILABLE = "AVAILABLE", _("Available")
    RENTED = "RENTED", _("Rented")
    MAINTENANCE = "MAINTENANCE", _("Maintenance")
    SOLD = "SOLD", _("Satıldı")


class FuelType(models.TextChoices):
    """Araç yakıt tipi."""

    GASOLINE = "GASOLINE", _("Benzin")
    DIESEL = "DIESEL", _("Dizel")
    LPG = "LPG", _("LPG")
    HYBRID = "HYBRID", _("Hibrit")
    ELECTRIC = "ELECTRIC", _("Elektrik")


class Transmission(models.TextChoices):
    """Şanzıman tipi."""

    MANUAL = "MANUAL", _("Manuel")
    AUTOMATIC = "AUTOMATIC", _("Otomatik")
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC", _("Yarı Otomatik")


class BodyType(models.TextChoices):
    """Kasa tipi."""

    SEDAN = "SEDAN", _("Sedan")
    HATCHBACK = "HATCHBACK", _("Hatchback")
    STATION_WAGON = "STATION_WAGON", _("Station Wagon")
    SUV = "SUV", _("SUV")
    CROSSOVER = "CROSSOVER", _("Crossover")
    MINIVAN = "MINIVAN", _("Minivan")
    PICKUP = "PICKUP", _("Pickup")
    VAN = "VAN", _("Panelvan")
    COUPE = "COUPE", _("Coupe")


class VehicleCondition(models.TextChoices):
    """Satın alma sırasındaki araç durumu."""

    NEW = "NEW", _("Sıfır")
    USED = "USED", _("İkinci El")



class Vehicle(models.Model):
    """A physical vehicle belonging to a company's fleet."""

    plate_number: str = models.CharField(
        _("plate number"),
        max_length=16,
        unique=True,
        help_text=_("License plate; unique across the platform."),
    )
    brand: str = models.CharField(_("brand"), max_length=64)
    model: str = models.CharField(_("model"), max_length=64)
    sipp_code: str = models.CharField(
        _("SIPP code"),
        max_length=4,
        blank=True,
        default="",
        db_index=True,
        help_text=_("ACRISS/SIPP 4 harfli kiralama sınıf kodu (ör. ECMR)."),
    )
    production_year: int = models.PositiveSmallIntegerField(_("production year"))
    current_km: int = models.PositiveIntegerField(
        _("current km"),
        default=0,
        help_text=_("Latest odometer reading in kilometers."),
    )
    status: str = models.CharField(
        _("status"),
        max_length=16,
        choices=VehicleStatus.choices,
        default=VehicleStatus.AVAILABLE,
        db_index=True,
    )

    # --- Genişletilmiş araç künyesi (opsiyonel; geriye dönük uyumlu) ------
    package: str = models.CharField(_("package"), max_length=64, blank=True, default="")
    fuel_type: str = models.CharField(
        _("fuel type"),
        max_length=16,
        choices=FuelType.choices,
        blank=True,
        default="",
    )
    transmission: str = models.CharField(
        _("transmission"),
        max_length=16,
        choices=Transmission.choices,
        blank=True,
        default="",
    )
    engine_displacement_cc: int | None = models.PositiveIntegerField(
        _("engine displacement (cc)"), null=True, blank=True
    )
    engine_power_hp: int | None = models.PositiveIntegerField(
        _("engine power (hp)"), null=True, blank=True
    )
    segment: str = models.CharField(
        _("segment"),
        max_length=32,
        blank=True,
        default="",
        help_text=_("Ticari segment etiketi (ör. B, C, SUV)."),
    )
    body_type: str = models.CharField(
        _("body type"),
        max_length=16,
        choices=BodyType.choices,
        blank=True,
        default="",
    )
    color: str = models.CharField(_("color"), max_length=32, blank=True, default="")
    chassis_number: str = models.CharField(
        _("chassis number"), max_length=32, blank=True, default=""
    )
    registration_number: str = models.CharField(
        _("registration number"), max_length=32, blank=True, default=""
    )

    # --- TCO (Toplam Sahiplik Maliyeti) — optimum satış & maliyet analizi ------
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
        verbose_name = _("vehicle")
        verbose_name_plural = _("vehicles")
        ordering = ("plate_number",)
        indexes = (
            models.Index(fields=("company", "status")),
            models.Index(fields=("plate_number",)),
        )

    def __str__(self) -> str:
        return f"{self.plate_number} — {self.brand} {self.model}"


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
        verbose_name = _("vehicle live state")
        verbose_name_plural = _("vehicle live states")

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} @ ({self.latitude:.5f}, {self.longitude:.5f})"

