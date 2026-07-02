"""Relational (PostgreSQL / OLTP) domain models for RentA-Fleet PRO.

This module holds the authoritative, transactional source of truth:
tenants (``Company``), their users (``CustomUser``) and the physical
fleet (``Vehicle``). High-volume, append-only telemetry does **not** live
here — it is streamed into ClickHouse (see ``api/clickhouse_client.py`` and
``api/sql/clickhouse_telemetry_logs.sql``).
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    """Kurumsal roller (single-tenant B2B panel).

    - ``FLEET_MANAGER``: Şirket sahibi / filo müdürü; tüm analitik ve finans.
    - ``OPERATIONS_STAFF``: Operasyon personeli; araç, harita ve bakım.
    """

    FLEET_MANAGER = "FLEET_MANAGER", _("Filo Müdürü")
    OPERATIONS_STAFF = "OPERATIONS_STAFF", _("Operasyon Personeli")


class VehicleStatus(models.TextChoices):
    """Lifecycle state of a fleet vehicle."""

    AVAILABLE = "AVAILABLE", _("Available")
    RENTED = "RENTED", _("Rented")
    MAINTENANCE = "MAINTENANCE", _("Maintenance")


class Company(models.Model):
    """Kurulum başına tek kiracı şirket (single-tenant).

    Her müşteri kurulumunda bir şirket kaydı bulunur; kullanıcılar ve
    araçlar bu şirkete bağlanır.
    """

    name: str = models.CharField(_("company name"), max_length=255)
    tax_number: str = models.CharField(
        _("tax number"),
        max_length=32,
        unique=True,
        help_text=_("Government-issued tax identifier; unique per tenant."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("company")
        verbose_name_plural = _("companies")
        ordering = ("name",)
        indexes = (models.Index(fields=("tax_number",)),)

    def __str__(self) -> str:
        return f"{self.name} ({self.tax_number})"


class CustomUser(AbstractUser):
    """Platform user extending Django's ``AbstractUser``.

    Adds a ``role`` for authorization and a ``company`` link so every
    staff user is scoped to the single tenant installation.
    """

    role: str = models.CharField(
        _("role"),
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.OPERATIONS_STAFF,
        db_index=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
        verbose_name=_("company"),
        help_text=_("Bu kurulumdaki kiracı şirket."),
    )

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    @property
    def is_fleet_manager(self) -> bool:
        return self.role == UserRole.FLEET_MANAGER

    @property
    def is_operations_staff(self) -> bool:
        return self.role == UserRole.OPERATIONS_STAFF

    def __str__(self) -> str:
        return f"{self.get_username()} [{self.get_role_display()}]"


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


class Gender(models.TextChoices):
    """Sürücü cinsiyet bilgisi."""

    MALE = "MALE", _("Erkek")
    FEMALE = "FEMALE", _("Kadın")
    OTHER = "OTHER", _("Diğer")


class RentalStatus(models.TextChoices):
    """Kiralama kaydının yaşam döngüsü."""

    ACTIVE = "ACTIVE", _("Aktif")
    COMPLETED = "COMPLETED", _("Tamamlandı")
    CANCELLED = "CANCELLED", _("İptal")


class Driver(models.Model):
    """Araç kiralayan gerçek kişi (müşteri sürücü).

    Panel kullanıcıları (CustomUser) değildir; kiralama şirketinin müşterileridir.
    Sürüş skoru kişiye özeldir ve telemetri + kiralama dönemlerinden hesaplanır.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="drivers",
        verbose_name=_("company"),
    )
    first_name: str = models.CharField(_("first name"), max_length=64)
    last_name: str = models.CharField(_("last name"), max_length=64)
    national_id: str = models.CharField(
        _("national ID"),
        max_length=11,
        unique=True,
        help_text=_("T.C. kimlik numarası."),
    )
    gender: str = models.CharField(
        _("gender"),
        max_length=8,
        choices=Gender.choices,
        default=Gender.MALE,
    )
    birth_date = models.DateField(_("birth date"))
    phone: str = models.CharField(_("phone"), max_length=20)
    email: str = models.EmailField(_("email"), blank=True)
    license_number: str = models.CharField(_("license number"), max_length=32)
    license_class: str = models.CharField(
        _("license class"),
        max_length=8,
        default="B",
        help_text=_("Ehliyet sınıfı (B, BE, C vb.)."),
    )
    city: str = models.CharField(_("city"), max_length=64)
    district: str = models.CharField(_("district"), max_length=64, blank=True)
    address: str = models.CharField(_("address"), max_length=255, blank=True)
    is_blacklisted: bool = models.BooleanField(
        _("blacklisted"),
        default=False,
        help_text=_("Kara listedeki sürücülere yeni kiralama yapılmamalı."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("driver")
        verbose_name_plural = _("drivers")
        ordering = ("last_name", "first_name")
        indexes = (
            models.Index(fields=("company", "last_name")),
            models.Index(fields=("national_id",)),
        )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.national_id})"


class Rental(models.Model):
    """Bir sürücünün belirli bir araçtaki kiralama dönemi.

    Telemetri skorlaması yalnızca bu dönemdeki (started_at–ended_at) kayıtları
    sürücüye yazar; araç başka sürücüye geçince skorlar karışmaz.
    """

    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name="rentals",
        verbose_name=_("driver"),
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="rentals",
        verbose_name=_("vehicle"),
    )
    status: str = models.CharField(
        _("status"),
        max_length=16,
        choices=RentalStatus.choices,
        default=RentalStatus.ACTIVE,
        db_index=True,
    )
    started_at = models.DateTimeField(_("started at"))
    ended_at = models.DateTimeField(_("ended at"), null=True, blank=True)
    start_km: int = models.PositiveIntegerField(_("start km"), default=0)
    end_km = models.PositiveIntegerField(_("end km"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("rental")
        verbose_name_plural = _("rentals")
        ordering = ("-started_at",)
        indexes = (
            models.Index(fields=("driver", "status")),
            models.Index(fields=("vehicle", "status")),
        )

    def __str__(self) -> str:
        return f"{self.driver} → {self.vehicle.plate_number} [{self.status}]"


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
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("competitor price")
        verbose_name_plural = _("competitor prices")
        ordering = ("source_name",)
        constraints = (
            models.UniqueConstraint(
                fields=("vehicle", "external_reference"),
                condition=~models.Q(external_reference=""),
                name="uniq_competitor_price_vehicle_ext_ref",
            ),
        )
        indexes = (
            models.Index(fields=("vehicle", "sipp_code")),
        )

    def __str__(self) -> str:
        return f"{self.source_name}: {self.daily_price} TL → {self.vehicle.plate_number}"
