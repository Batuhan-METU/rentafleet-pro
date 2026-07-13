"""Kiralama gelir modeli — araç bazlı gelir kayıtları."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.reservations.models import Rental
from backend.apps.vehicles.models import Vehicle


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
        app_label = "api"
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
