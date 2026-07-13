"""Rental reservation models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.customer_profiles.models import Driver
from backend.apps.reservations.choices import RentalStatus, ReturnStatus
from backend.apps.vehicles.models import Vehicle

__all__ = ["Rental", "RentalStatus", "ReturnStatus"]


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
    ended_at = models.DateTimeField(
        _("ended at"),
        null=True,
        blank=True,
        help_text=_("Güncel planlanan dönüş tarihi; uzatma yapılırsa ileri taşınır."),
    )
    original_ended_at = models.DateTimeField(
        _("original ended at"),
        null=True,
        blank=True,
        help_text=_(
            "Oluşturmada belirlenen ilk sözleşme dönüş tarihi — uzatmayla asla "
            "değişmez; erken/geç/zamanında sınıflandırması buna göre yapılır."
        ),
    )
    start_km: int = models.PositiveIntegerField(_("start km"), default=0)
    end_km = models.PositiveIntegerField(_("end km"), null=True, blank=True)
    application = models.ForeignKey(
        "api.RentalApplication",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_rentals",
        verbose_name=_("rental application"),
    )
    deposit_amount = models.DecimalField(
        _("deposit amount"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    quoted_total = models.DecimalField(
        _("quoted total"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    daily_rate = models.DecimalField(
        _("daily rate"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Anlaşılan günlük kiralama bedeli — tüm fiyat farkı hesaplarının tek kaynağı."),
    )
    actual_return_at = models.DateTimeField(
        _("actual return at"),
        null=True,
        blank=True,
        help_text=_("Aracın fiilen teslim alındığı an; ended_at sözleşme tarihidir."),
    )
    price_difference = models.DecimalField(
        _("price difference"),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Pozitif = ek tahsilat (geç teslim), negatif = iade (erken teslim)."),
    )
    return_status = models.CharField(
        _("return status"),
        max_length=16,
        choices=ReturnStatus.choices,
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        app_label = "api"
        db_table = "api_rental"
        verbose_name = _("rental")
        verbose_name_plural = _("rentals")
        ordering = ("-started_at",)
        indexes = (
            models.Index(fields=("driver", "status")),
            models.Index(fields=("vehicle", "status")),
        )

    def __str__(self) -> str:
        return f"{self.driver} → {self.vehicle.plate_number} [{self.status}]"

