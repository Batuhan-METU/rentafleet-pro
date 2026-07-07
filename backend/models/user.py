"""Platform user models."""
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from .company import Company

class UserRole(models.TextChoices):
    """Kurumsal roller (single-tenant B2B panel).

    - ``FLEET_MANAGER``: Şirket sahibi / filo müdürü; tüm analitik ve finans.
    - ``OPERATIONS_STAFF``: Operasyon personeli; araç, harita ve bakım.
    """

    FLEET_MANAGER = "FLEET_MANAGER", _("Filo Müdürü")
    OPERATIONS_STAFF = "OPERATIONS_STAFF", _("Operasyon Personeli")



class CustomUser(AbstractUser):
    """Platform user extending Django's ``AbstractUser``.

    Adds a ``role`` for authorization and a ``company`` link so every
    staff user is scoped to the single tenant installation.
    """

    role: str = models.CharField(
        _("role"),
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.OPERATIONS_STAFF,
        db_index=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
        verbose_name=_("company"),
        help_text=_("Bu kurulumdaki kiracı şirket."),
    )

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    @property
    def is_fleet_manager(self) -> bool:
        return self.role == UserRole.FLEET_MANAGER

    @property
    def is_operations_staff(self) -> bool:
        return self.role == UserRole.OPERATIONS_STAFF

    def __str__(self) -> str:
        return f"{self.get_username()} [{self.get_role_display()}]"

