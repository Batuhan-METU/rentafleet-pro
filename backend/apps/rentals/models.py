"""Rental reservation models."""
from __future__ import annotations

from typing import Any

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.choices import RentalStatus, ReturnStatus
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
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("company"),
        help_text=_(
            "driver.company'nin denormalize kopyası — kiracı-kapsamlı sorgular "
            "(bkz. _rental_queryset/get_scoped_rental) driver üzerinden JOIN "
            "yapmadan doğrudan filtreleyebilsin diye. save() tarafından "
            "otomatik doldurulur, elle ayarlamaya gerek yoktur."
        ),
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="rentals",
        verbose_name=_("vehicle"),
    )
    status = models.CharField(
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
    start_km = models.PositiveIntegerField(_("start km"), default=0)
    end_km = models.PositiveIntegerField(_("end km"), null=True, blank=True)
    application = models.ForeignKey(
        "risk_checks.RentalApplication",
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
        db_table = "api_rental"
        verbose_name = _("rental")
        verbose_name_plural = _("rentals")
        # "-id" eşitlik bozucu (tiebreaker) olarak eklendi: started_at tek
        # başına benzersiz değil (aynı anda başlayan onlarca kiralama var) —
        # bir tiebreaker olmadan ORDER BY sonucu deterministik değildir, bu da
        # sayfalanan listelerde (Geçmiş sekmesi) aynı kaydın iki farklı
        # sayfada birden çıkmasına veya hiç çıkmamasına yol açar.
        ordering = ("-started_at", "-id")
        indexes = (
            models.Index(fields=("driver", "status")),
            models.Index(fields=("vehicle", "status")),
            models.Index(fields=("company", "status"), name="rentals_company_status_idx"),
        )

    def __str__(self) -> str:
        return f"{self.driver} → {self.vehicle.plate_number} [{self.status}]"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # `company` driver.company'nin bilinçli bir denormalizasyonu (bkz.
        # alan yorumu) — her çağıranın bunu elle set etmesini beklemek yerine
        # (unutulursa tutarsız veri riski) invariant'ı burada, TEK yerde
        # garanti ederiz. Mevcut TÜM `Rental.objects.create(...)` çağrıları
        # (üretim kodu + testler) hiç değişmeden doğru çalışmaya devam eder.
        if self.company_id is None:
            self.company_id = self.driver.company_id
        super().save(*args, **kwargs)

