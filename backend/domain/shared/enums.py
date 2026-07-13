"""Paylaşılan domain enum'ları — değerlerin tek kaynağı.

Django model alanları için `backend.apps.risk_checks.choices` bu enum'ları
TextChoices olarak sarmalar (etiket çevirileri orada).
"""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class RuleEffect(StrEnum):
    ADD_SCORE = "ADD_SCORE"
    BLOCK = "BLOCK"
    WARN = "WARN"
    SET_LEVEL = "SET_LEVEL"


class VehicleTier(StrEnum):
    PREMIUM = "PREMIUM"
    STANDARD = "STANDARD"
    ECONOMY = "ECONOMY"