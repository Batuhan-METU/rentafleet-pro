"""Araç gider modeli — tekil ve tekrarlayan masraflar."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.floor_pricing.choices import ExpenseCategory, ExpenseRecurrence
from backend.apps.vehicles.models import Vehicle


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
        app_label = "api"
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
        if self.category == ExpenseCategory.DIGER and self.custom_label:
            return self.custom_label
        return self.get_category_display()

    def __str__(self) -> str:
        return f"{self.label}: {self.amount} TL → {self.vehicle.plate_number}"
