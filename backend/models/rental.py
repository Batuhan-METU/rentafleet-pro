"""Rental reservation models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from .driver import Driver
from .vehicle import Vehicle

class RentalStatus(models.TextChoices):
    """Kiralama kaydının yaşam döngüsü."""

    ACTIVE = "ACTIVE", _("Aktif")
    COMPLETED = "COMPLETED", _("Tamamlandı")
    CANCELLED = "CANCELLED", _("İptal")



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

