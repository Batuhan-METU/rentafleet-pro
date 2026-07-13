"""Başvuru ve karar log modelleri."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.risk_checks.choices import (
    DecisionStep,
    RentalApplicationStatus,
    RiskLevel,
    RuleEngineType,
)


class RentalApplication(models.Model):
    """Kiralama karar başvurusu — yaşam döngüsü kaydı."""

    company = models.ForeignKey(
        "api.Company",
        on_delete=models.CASCADE,
        related_name="rental_applications",
    )
    driver = models.ForeignKey(
        "api.Driver",
        on_delete=models.CASCADE,
        related_name="rental_applications",
    )
    status = models.CharField(
        max_length=24,
        choices=RentalApplicationStatus.choices,
        default=RentalApplicationStatus.DRAFT,
        db_index=True,
    )
    is_first_rental = models.BooleanField(default=True)
    requested_pickup_at = models.DateTimeField(null=True, blank=True)
    requested_return_at = models.DateTimeField(null=True, blank=True)
    assigned_vehicle = models.ForeignKey(
        "api.Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rental_applications",
    )
    created_by = models.ForeignKey(
        "api.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_rental_applications",
    )
    risk_score = models.PositiveSmallIntegerField(null=True, blank=True)
    risk_level = models.CharField(
        max_length=16,
        choices=RiskLevel.choices,
        blank=True,
        default="",
    )
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quoted_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "api"
        db_table = "api_rentalapplication"
        verbose_name = _("rental application")
        verbose_name_plural = _("rental applications")
        ordering = ("-created_at",)
        indexes = (
            models.Index(fields=("company", "status")),
            models.Index(fields=("driver", "status")),
        )


class RentalDecisionLog(models.Model):
    """Değiştirilemez karar audit kaydı."""

    application = models.ForeignKey(
        RentalApplication,
        on_delete=models.CASCADE,
        related_name="decision_logs",
    )
    step = models.CharField(max_length=16, choices=DecisionStep.choices)
    engine = models.CharField(max_length=16, choices=RuleEngineType.choices, blank=True, default="")
    input_snapshot = models.JSONField(default=dict)
    output_snapshot = models.JSONField(default=dict)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    risk_level = models.CharField(max_length=16, choices=RiskLevel.choices, blank=True, default="")
    approved = models.BooleanField(null=True, blank=True)
    rule_version = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "api"
        db_table = "api_rentaldecisionlog"
        verbose_name = _("rental decision log")
        verbose_name_plural = _("rental decision logs")
        ordering = ("created_at",)
