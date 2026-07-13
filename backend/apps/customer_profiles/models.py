"""Customer driver models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.customer_profiles.choices import Gender
from backend.apps.companies.models import Company

__all__ = ["Driver", "Gender"]


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
    is_whitelisted: bool = models.BooleanField(_("whitelisted"), default=False)
    vip_tier: str = models.CharField(
        _("VIP tier"),
        max_length=16,
        default="NONE",
        blank=True,
    )
    loyalty_level: int = models.PositiveSmallIntegerField(_("loyalty level"), default=0)
    occupation: str = models.CharField(_("occupation"), max_length=128, blank=True, default="")
    employer: str = models.CharField(_("employer"), max_length=128, blank=True, default="")
    monthly_income = models.DecimalField(
        _("monthly income"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    marital_status: str = models.CharField(
        _("marital status"),
        max_length=16,
        blank=True,
        default="",
    )
    children_count: int = models.PositiveSmallIntegerField(_("children count"), default=0)
    education_level: str = models.CharField(
        _("education level"),
        max_length=16,
        blank=True,
        default="",
    )
    citizenship: str = models.CharField(_("citizenship"), max_length=64, blank=True, default="TR")
    is_foreign: bool = models.BooleanField(_("foreign national"), default=False)
    residence_duration_months: int = models.PositiveIntegerField(
        _("residence duration months"),
        default=0,
    )
    lifetime_value = models.DecimalField(
        _("lifetime value"),
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    current_customer_score = models.PositiveSmallIntegerField(
        _("current customer score"),
        null=True,
        blank=True,
    )
    current_risk_score = models.PositiveSmallIntegerField(
        _("current risk score"),
        null=True,
        blank=True,
    )
    current_driving_score = models.PositiveSmallIntegerField(
        _("current driving score"),
        null=True,
        blank=True,
    )
    risk_note: str = models.TextField(_("risk note"), blank=True, default="")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        app_label = "api"
        db_table = "api_driver"
        verbose_name = _("driver")
        verbose_name_plural = _("drivers")
        ordering = ("last_name", "first_name")
        indexes = (
            models.Index(fields=("company", "last_name")),
            models.Index(fields=("national_id",)),
        )
        constraints = (
            models.UniqueConstraint(
                fields=("company", "national_id"),
                name="uniq_driver_national_id_per_company",
            ),
        )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __str__(self) -> str:
        return f"{self.full_name} ({self.national_id})"

