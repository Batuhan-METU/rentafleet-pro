"""Araç finansal profil modeli — satın alma, fiyat yapısı, çıkış planı."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.vehicles.models import Vehicle, VehicleCondition


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
        app_label = "api"
        db_table = "api_vehiclefinancialprofile"
        verbose_name = _("vehicle financial profile")
        verbose_name_plural = _("vehicle financial profiles")

    def __str__(self) -> str:
        return f"Finans profili — {self.vehicle.plate_number}"
