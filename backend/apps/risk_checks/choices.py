"""Karar destek TextChoices — Django model alanları için etiketli seçenekler.

RiskLevel, RuleEffect ve VehicleTier değerleri `backend.domain.shared.enums`
üzerinden gelir; burada yalnızca çeviri etiketleri eklenir.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from backend.domain.shared.enums import RiskLevel as RiskLevelValue
from backend.domain.shared.enums import RuleEffect as RuleEffectValue
from backend.domain.shared.enums import VehicleTier as VehicleTierValue


class VipTier(models.TextChoices):
    NONE = "NONE", _("Yok")
    SILVER = "SILVER", _("Gümüş")
    GOLD = "GOLD", _("Altın")
    PLATINUM = "PLATINUM", _("Platin")


class MaritalStatus(models.TextChoices):
    SINGLE = "SINGLE", _("Bekar")
    MARRIED = "MARRIED", _("Evli")
    DIVORCED = "DIVORCED", _("Boşanmış")
    WIDOWED = "WIDOWED", _("Dul")


class EducationLevel(models.TextChoices):
    PRIMARY = "PRIMARY", _("İlkokul")
    SECONDARY = "SECONDARY", _("Ortaokul")
    HIGH_SCHOOL = "HIGH_SCHOOL", _("Lise")
    ASSOCIATE = "ASSOCIATE", _("Ön Lisans")
    BACHELOR = "BACHELOR", _("Lisans")
    MASTER = "MASTER", _("Yüksek Lisans")
    DOCTORATE = "DOCTORATE", _("Doktora")


class RuleEngineType(models.TextChoices):
    RISK = "RISK", _("Risk")
    ELIGIBILITY = "ELIGIBILITY", _("Araç Uygunluk")
    PRICING = "PRICING", _("Fiyatlandırma")
    DEPOSIT = "DEPOSIT", _("Depozito")
    DRIVING = "DRIVING", _("Sürüş Skoru")


class RuleEffect(models.TextChoices):
    ADD_SCORE = RuleEffectValue.ADD_SCORE, _("Skor Ekle")
    BLOCK = RuleEffectValue.BLOCK, _("Engelle")
    WARN = RuleEffectValue.WARN, _("Uyarı")
    SET_LEVEL = RuleEffectValue.SET_LEVEL, _("Seviye Ata")


class RiskLevel(models.TextChoices):
    VERY_LOW = RiskLevelValue.VERY_LOW, _("Çok Düşük")
    LOW = RiskLevelValue.LOW, _("Düşük")
    MEDIUM = RiskLevelValue.MEDIUM, _("Orta")
    HIGH = RiskLevelValue.HIGH, _("Yüksek")
    VERY_HIGH = RiskLevelValue.VERY_HIGH, _("Çok Yüksek")


class RentalApplicationStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Taslak")
    IDENTITY_CAPTURED = "IDENTITY_CAPTURED", _("Kimlik Alındı")
    LICENSE_CAPTURED = "LICENSE_CAPTURED", _("Ehliyet Alındı")
    PROFILE_CAPTURED = "PROFILE_CAPTURED", _("Profil Alındı")
    FINANCIAL_CAPTURED = "FINANCIAL_CAPTURED", _("Finans Alındı")
    EVALUATED = "EVALUATED", _("Değerlendirildi")
    QUOTED = "QUOTED", _("Fiyatlandırıldı")
    APPROVED = "APPROVED", _("Onaylandı")
    REJECTED = "REJECTED", _("Reddedildi")
    HANDED_OVER = "HANDED_OVER", _("Teslim Edildi")
    COMPLETED = "COMPLETED", _("Tamamlandı")
    CANCELLED = "CANCELLED", _("İptal")


class DecisionStep(models.TextChoices):
    INTAKE = "INTAKE", _("Kayıt")
    IDENTITY = "IDENTITY", _("Kimlik")
    LICENSE = "LICENSE", _("Ehliyet")
    PROFILE = "PROFILE", _("Profil")
    FINANCIAL = "FINANCIAL", _("Finans")
    RISK = "RISK", _("Risk")
    ELIGIBILITY = "ELIGIBILITY", _("Uygunluk")
    PRICING = "PRICING", _("Fiyat")
    DEPOSIT = "DEPOSIT", _("Depozito")
    FINAL = "FINAL", _("Final")


class VehicleTier(models.TextChoices):
    PREMIUM = VehicleTierValue.PREMIUM, _("Premium")
    STANDARD = VehicleTierValue.STANDARD, _("Standart")
    ECONOMY = VehicleTierValue.ECONOMY, _("Ekonomi")
