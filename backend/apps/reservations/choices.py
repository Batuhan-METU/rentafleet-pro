"""Kiralama TextChoices tanımları."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class RentalStatus(models.TextChoices):
    """Kiralama kaydının yaşam döngüsü."""

    ACTIVE = "ACTIVE", _("Aktif")
    COMPLETED = "COMPLETED", _("Tamamlandı")
    CANCELLED = "CANCELLED", _("İptal")


class ReturnStatus(models.TextChoices):
    """Araç teslim alma anındaki zamanlama sınıflandırması."""

    ON_TIME = "ON_TIME", _("Zamanında")
    EARLY = "EARLY", _("Erken")
    LATE = "LATE", _("Geç")
