"""Company tenant model."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

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
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("company")
        verbose_name_plural = _("companies")
        ordering = ("name",)
        indexes = (models.Index(fields=("tax_number",)),)

    def __str__(self) -> str:
        return f"{self.name} ({self.tax_number})"

