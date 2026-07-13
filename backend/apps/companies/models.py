"""Şirket ve platform kullanıcı modelleri."""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.companies.choices import UserRole

__all__ = ["Company", "CustomUser", "UserRole"]


class Company(models.Model):
    """Platformdaki bir müşteri şirket (multi-tenant kiracı birimi).

    Kurulum çok-kiracılıdır (shared DB, subdomain bazlı çözümleme —
    bkz. ``backend.common.middleware.company_router``); her ``Company``
    kaydı bir şirketi temsil eder ve ilişkili tüm veriler bu FK ile
    izole edilir.
    """

    name: str = models.CharField(_("company name"), max_length=255)
    tax_number: str = models.CharField(
        _("tax number"),
        max_length=32,
        unique=True,
        help_text=_("Government-issued tax identifier; unique per company."),
    )
    display_name: str = models.CharField(
        _("display name"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("Arayüzde görünen ticari marka adı (white-label)."),
    )
    logo_url: str | None = models.URLField(
        _("logo URL"),
        max_length=512,
        blank=True,
        null=True,
        help_text=_("Şirket logosu görsel adresi."),
    )
    primary_color: str = models.CharField(
        _("primary color"),
        max_length=7,
        default="#3B82F6",
        help_text=_("Panel ana renk kodu (hex)."),
    )
    secondary_color: str = models.CharField(
        _("secondary color"),
        max_length=7,
        default="#1E3A8A",
        help_text=_("Menü / yan panel renk kodu (hex)."),
    )
    description: str = models.TextField(
        _("company description"),
        blank=True,
        default="",
        help_text=_("Genel bakış ve ayarlar ekranında gösterilen şirket tanıtımı."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        app_label = "api"
        db_table = "api_company"
        verbose_name = _("company")
        verbose_name_plural = _("companies")
        ordering = ("name",)
        indexes = (models.Index(fields=("tax_number",)),)

    def __str__(self) -> str:
        return f"{self.name} ({self.tax_number})"


class CustomUser(AbstractUser):
    """Platform user extending Django's ``AbstractUser``."""

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
        app_label = "api"
        db_table = "api_customuser"
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
