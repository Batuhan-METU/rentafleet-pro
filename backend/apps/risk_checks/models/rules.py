"""Kural motoru modelleri."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.apps.risk_checks.choices import RuleEffect, RuleEngineType


class RuleSet(models.Model):
    company = models.ForeignKey(
        "api.Company",
        on_delete=models.CASCADE,
        related_name="rule_sets",
    )
    engine = models.CharField(max_length=16, choices=RuleEngineType.choices, db_index=True)
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=32, default="1.0.0")
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "api"
        db_table = "api_ruleset"
        verbose_name = _("rule set")
        verbose_name_plural = _("rule sets")
        constraints = (
            models.UniqueConstraint(
                fields=("company", "engine", "version"),
                name="uniq_rule_set_company_engine_version",
            ),
        )


class RuleDefinition(models.Model):
    rule_set = models.ForeignKey(
        RuleSet,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    code = models.CharField(max_length=64)
    priority = models.PositiveSmallIntegerField(default=100)
    effect = models.CharField(max_length=16, choices=RuleEffect.choices)
    points = models.SmallIntegerField(default=0)
    message = models.CharField(max_length=255)
    condition = models.JSONField(default=dict, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "api"
        db_table = "api_ruledefinition"
        verbose_name = _("rule definition")
        verbose_name_plural = _("rule definitions")
        ordering = ("priority", "code")
        constraints = (
            models.UniqueConstraint(
                fields=("rule_set", "code"),
                name="uniq_rule_code_per_set",
            ),
        )
