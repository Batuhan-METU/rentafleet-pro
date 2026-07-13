"""Filo araç TextChoices tanımları."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class VehicleStatus(models.TextChoices):
    """Lifecycle state of a fleet vehicle."""

    AVAILABLE = "AVAILABLE", _("Available")
    RENTED = "RENTED", _("Rented")
    MAINTENANCE = "MAINTENANCE", _("Maintenance")
    SOLD = "SOLD", _("Satıldı")


class FuelType(models.TextChoices):
    """Araç yakıt tipi."""

    GASOLINE = "GASOLINE", _("Benzin")
    DIESEL = "DIESEL", _("Dizel")
    LPG = "LPG", _("LPG")
    HYBRID = "HYBRID", _("Hibrit")
    ELECTRIC = "ELECTRIC", _("Elektrik")


class Transmission(models.TextChoices):
    """Şanzıman tipi."""

    MANUAL = "MANUAL", _("Manuel")
    AUTOMATIC = "AUTOMATIC", _("Otomatik")
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC", _("Yarı Otomatik")


class BodyType(models.TextChoices):
    """Kasa tipi."""

    SEDAN = "SEDAN", _("Sedan")
    HATCHBACK = "HATCHBACK", _("Hatchback")
    STATION_WAGON = "STATION_WAGON", _("Station Wagon")
    SUV = "SUV", _("SUV")
    CROSSOVER = "CROSSOVER", _("Crossover")
    MINIVAN = "MINIVAN", _("Minivan")
    PICKUP = "PICKUP", _("Pickup")
    VAN = "VAN", _("Panelvan")
    COUPE = "COUPE", _("Coupe")


class VehicleCondition(models.TextChoices):
    """Satın alma sırasındaki araç durumu."""

    NEW = "NEW", _("Sıfır")
    USED = "USED", _("İkinci El")
