"""Risk analizi modelleri."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.risk_checks.choices import RiskLevel, VehicleTier
from backend.apps.risk_checks.models.submissions import RentalApplication


class CustomerRiskSnapshot(models.Model):
    driver = models.ForeignKey(
        "api.Driver",
        on_delete=models.CASCADE,
        related_name="risk_snapshots",
    )
    application = models.ForeignKey(
        RentalApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_snapshots",
    )
    risk_score = models.PositiveSmallIntegerField()
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices)
    factor_breakdown = models.JSONField(default=dict)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "api"
        db_table = "api_customerrisksnapshot"
        verbose_name = _("customer risk snapshot")
        verbose_name_plural = _("customer risk snapshots")
        ordering = ("-computed_at",)


class VehicleRiskTier(models.Model):
    vehicle = models.OneToOneField(
        "api.Vehicle",
        on_delete=models.CASCADE,
        related_name="risk_tier",
    )
    tier = models.CharField(max_length=16, choices=VehicleTier.choices, default=VehicleTier.STANDARD)
    min_risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        default=RiskLevel.VERY_LOW,
    )
    max_risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        default=RiskLevel.HIGH,
    )

    class Meta:
        app_label = "api"
        db_table = "api_vehiclerisktier"
        verbose_name = _("vehicle risk tier")
        verbose_name_plural = _("vehicle risk tiers")
