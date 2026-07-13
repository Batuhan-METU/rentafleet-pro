"""Financial and market pricing models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.vehicles.models import Vehicle


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
    pickup_date = models.DateField(
        _("pickup date"),
        db_index=True,
        help_text=_("Piyasa fiyatının geçerli olduğu kiralama başlangıç tarihi."),
    )
    dropoff_date = models.DateField(
        _("dropoff date"),
        db_index=True,
        help_text=_("Piyasa fiyatının geçerli olduğu kiralama bitiş tarihi."),
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        app_label = "api"
        db_table = "api_competitorprice"
        verbose_name = _("competitor price")
        verbose_name_plural = _("competitor prices")
        ordering = ("source_name",)
        constraints = (
            models.UniqueConstraint(
                fields=("vehicle", "external_reference", "pickup_date", "dropoff_date"),
                condition=~models.Q(external_reference=""),
                name="uniq_competitor_price_vehicle_ext_ref_window",
            ),
        )
        indexes = (
            models.Index(fields=("vehicle", "sipp_code")),
            models.Index(fields=("pickup_date", "dropoff_date")),
        )

    def __str__(self) -> str:
        return f"{self.source_name}: {self.daily_price} TL → {self.vehicle.plate_number}"


class EnuygunMarketSnapshot(models.Model):
    """Enuygun API çekimi — her kiralama penceresi (alış/dönüş) için bir kayıt."""

    snapshot_date = models.DateField(_("snapshot date"), db_index=True)
    city = models.CharField(_("city"), max_length=64)
    pickup_date = models.DateField(_("pickup date"), db_index=True)
    dropoff_date = models.DateField(_("dropoff date"), db_index=True)
    fetched_at = models.DateTimeField(_("fetched at"), auto_now_add=True)
    reservation_count = models.PositiveIntegerField(_("reservation count"), default=0)

    class Meta:
        app_label = "api"
        db_table = "api_enuygunmarketsnapshot"
        verbose_name = _("Enuygun market snapshot")
        verbose_name_plural = _("Enuygun market snapshots")
        ordering = ("-pickup_date", "-fetched_at")
        constraints = (
            models.UniqueConstraint(
                fields=("pickup_date", "dropoff_date", "city"),
                name="uniq_market_snapshot_rental_window",
            ),
        )

    def __str__(self) -> str:
        return f"{self.city} @ {self.snapshot_date} ({self.reservation_count} kayıt)"


class EnuygunCachedReservation(models.Model):
    """Enuygun'dan alınan ham rezervasyon satırı (günlük snapshot)."""

    snapshot = models.ForeignKey(
        EnuygunMarketSnapshot,
        on_delete=models.CASCADE,
        related_name="reservations",
        verbose_name=_("snapshot"),
    )
    reference_id = models.CharField(_("reference id"), max_length=64)
    provider = models.CharField(_("provider"), max_length=64)
    brand = models.CharField(_("brand"), max_length=64)
    model = models.CharField(_("model"), max_length=128)
    segment = models.CharField(_("segment"), max_length=4, blank=True, default="")
    vehicle_class = models.CharField(_("vehicle class"), max_length=64, blank=True, default="")
    fuel = models.CharField(_("fuel"), max_length=64, blank=True, default="")
    transmission = models.CharField(_("transmission"), max_length=32, blank=True, default="")
    daily_price = models.DecimalField(_("daily price"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=8, default="TRY")

    class Meta:
        app_label = "api"
        db_table = "api_enuyguncachedreservation"
        verbose_name = _("cached Enuygun reservation")
        verbose_name_plural = _("cached Enuygun reservations")
        ordering = ("provider", "brand", "model")
        constraints = (
            models.UniqueConstraint(
                fields=("snapshot", "reference_id"),
                name="uniq_cached_reservation_per_snapshot",
            ),
        )
        indexes = (
            models.Index(fields=("snapshot", "segment")),
        )

    def __str__(self) -> str:
        return f"{self.provider} — {self.brand} {self.model} @ {self.daily_price} {self.currency}"

    def to_reservation_dict(self) -> dict:
        """Segment filtresi için API formatına yakın sözlük."""
        return {
            "referenceId": self.reference_id,
            "vehicle": {
                "brand": self.brand,
                "name": self.model,
                "class": self.vehicle_class,
                "fuel": self.fuel,
                "transmission": self.transmission,
                "sippCode": None,
            },
            "company": {"name": self.provider},
            "price": {
                "dailyPrice": float(self.daily_price),
                "currency": self.currency,
            },
        }


# ======================================================================
# FİNANSAL KARAR DESTEK MODELLERİ
# ----------------------------------------------------------------------
# Bir araç kiralama şirketinin araç başına gerçek kârını modellemek için:
#   * VehicleFinancialProfile — satın alma + kiralama fiyat yapısı + beklenen kullanım
#   * VehicleExpense           — tek seferlik veya tekrarlayan giderler
#   * RentalIncome             — araç bazlı kiralama gelirleri
# Tüm parasal alanlar DecimalField'tir; hesaplamalar servis katmanında yapılır.
# ======================================================================
