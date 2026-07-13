"""Müşteri / sürücü TextChoices tanımları."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class Gender(models.TextChoices):
    """Sürücü cinsiyet bilgisi."""

    MALE = "MALE", _("Erkek")
    FEMALE = "FEMALE", _("Kadın")
    OTHER = "OTHER", _("Diğer")
