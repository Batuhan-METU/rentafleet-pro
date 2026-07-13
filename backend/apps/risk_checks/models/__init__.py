"""Karar destek modelleri — Django keşfi için tüm modeller buradan açılır."""

from backend.apps.risk_checks.choices import (
    DecisionStep,
    EducationLevel,
    MaritalStatus,
    RentalApplicationStatus,
    RiskLevel,
    RuleEffect,
    RuleEngineType,
    VehicleTier,
    VipTier,
)
from backend.apps.risk_checks.models.profiles import (
    CustomerFinancialProfile,
    CustomerIdentityProfile,
    CustomerLicenseProfile,
    CustomerRentalHistoryStats,
)
from backend.apps.risk_checks.models.risks import CustomerRiskSnapshot, VehicleRiskTier
from backend.apps.risk_checks.models.rules import RuleDefinition, RuleSet
from backend.apps.risk_checks.models.submissions import RentalApplication, RentalDecisionLog

__all__ = [
    "CustomerFinancialProfile",
    "CustomerIdentityProfile",
    "CustomerLicenseProfile",
    "CustomerRentalHistoryStats",
    "CustomerRiskSnapshot",
    "DecisionStep",
    "EducationLevel",
    "MaritalStatus",
    "RentalApplication",
    "RentalApplicationStatus",
    "RentalDecisionLog",
    "RiskLevel",
    "RuleDefinition",
    "RuleEffect",
    "RuleEngineType",
    "RuleSet",
    "VehicleRiskTier",
    "VehicleTier",
    "VipTier",
]
