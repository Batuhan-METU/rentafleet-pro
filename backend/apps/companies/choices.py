"""Şirket / platform kullanıcı TextChoices tanımları."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    """Kurumsal roller (multi-tenant B2B panel)."""

    FLEET_MANAGER = "FLEET_MANAGER", _("Filo Müdürü")
    OPERATIONS_STAFF = "OPERATIONS_STAFF", _("Operasyon Personeli")
