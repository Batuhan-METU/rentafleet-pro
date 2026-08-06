"""Financial and market pricing models."""
from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.vehicles.models import Vehicle


class CarValuation(models.Model):
    """TSB (Türkiye Sigortalar Birliği) Kasko Değer Listesi satırı.

    ``202607R1.xlsx`` gibi aylık TSB listelerinden ``import_kasko_values``
    komutuyla doldurulur. Geniş tablo (tip başına yıl sütunları) burada uzun
    forma normalize edilir: her (marka, tip, yıl) için tek kasko bedeli.

    Piyasa analizi araçları SIPP koduna göre değil, bu tablodan bulunan
    kasko bedelinin düştüğü değer segmentine (tier) göre eşleştirir —
    tedarikçilerin yanlış SIPP kodları ortalamayı artık kirletemez.
    """

    brand_code = models.PositiveIntegerField(_("brand code"), db_index=True)
    type_code = models.PositiveIntegerField(_("type code"))
    brand_name = models.CharField(_("brand name"), max_length=64, db_index=True)
    type_name = models.CharField(_("type name"), max_length=128)
    year = models.PositiveIntegerField(_("model year"))
    kasko_value = models.DecimalField(
        _("kasko value"),
        max_digits=14,
        decimal_places=2,
        help_text=_("TSB listesindeki kasko bedeli (TL)."),
    )

    class Meta:
        db_table = "api_carvaluation"
        verbose_name = _("car valuation")
        verbose_name_plural = _("car valuations")
        ordering = ("brand_name", "type_name", "-year")
        constraints = (
            models.UniqueConstraint(
                fields=("brand_code", "type_code", "year"),
                name="uniq_car_valuation_type_year",
            ),
        )
        indexes = (
            models.Index(fields=("brand_name", "year")),
        )

    def __str__(self) -> str:
        return f"{self.brand_name} {self.type_name} ({self.year}): {self.kasko_value} TL"


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
        help_text=_("Bilgi amaçlı denormalize ilan SIPP kodu; eşleştirmede kullanılmaz."),
    )
    match_basis = models.CharField(
        _("match basis"),
        max_length=16,
        blank=True,
        default="",
        help_text=_("Kaydın hangi bağımsız yöntemle üretildiği: SIPP | TSB_TYPE_CODE."),
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
        db_table = "api_competitorprice"
        verbose_name = _("competitor price")
        verbose_name_plural = _("competitor prices")
        ordering = ("source_name",)
        constraints = (
            # match_basis dahil: aynı Enuygun ilanı hem SIPP hem TSB tip
            # kodu yöntemiyle bağımsız olarak eşleşebilir — bu durumda iki
            # ayrı satır (iki match_basis) olarak saklanır.
            models.UniqueConstraint(
                fields=("vehicle", "external_reference", "pickup_date", "dropoff_date", "match_basis"),
                condition=~models.Q(external_reference=""),
                name="uniq_competitor_price_vehicle_ext_ref_window_basis",
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

