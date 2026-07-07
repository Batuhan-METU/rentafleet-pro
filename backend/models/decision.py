"""Kiralama karar destek modelleri (Rule Engine, başvuru, risk snapshot)."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


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
    ADD_SCORE = "ADD_SCORE", _("Skor Ekle")
    BLOCK = "BLOCK", _("Engelle")
    WARN = "WARN", _("Uyarı")
    SET_LEVEL = "SET_LEVEL", _("Seviye Ata")


class RiskLevel(models.TextChoices):
    VERY_LOW = "VERY_LOW", _("Çok Düşük")
    LOW = "LOW", _("Düşük")
    MEDIUM = "MEDIUM", _("Orta")
    HIGH = "HIGH", _("Yüksek")
    VERY_HIGH = "VERY_HIGH", _("Çok Yüksek")


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
    PREMIUM = "PREMIUM", _("Premium")
    STANDARD = "STANDARD", _("Standart")
    ECONOMY = "ECONOMY", _("Ekonomi")


class CustomerIdentityProfile(models.Model):
    """Kimlik doğrulama ve belge durumu."""

    driver = models.OneToOneField(
        "api.Driver",
        on_delete=models.CASCADE,
        related_name="identity_profile",
    )
    identity_verified = models.BooleanField(default=False)
    identity_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    passport_number = models.CharField(max_length=32, blank=True, default="")
    document_fraud_suspicion = models.BooleanField(default=False)
    manual_notes = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("customer identity profile")
        verbose_name_plural = _("customer identity profiles")


class CustomerLicenseProfile(models.Model):
    """Ehliyet detayları."""

    driver = models.OneToOneField(
        "api.Driver",
        on_delete=models.CASCADE,
        related_name="license_profile",
    )
    license_issue_date = models.DateField(null=True, blank=True)
    license_points = models.PositiveSmallIntegerField(default=0)
    license_penalty_count = models.PositiveSmallIntegerField(default=0)
    has_src_certificate = models.BooleanField(default=False)
    has_psychotechnical = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("customer license profile")
        verbose_name_plural = _("customer license profiles")


class CustomerFinancialProfile(models.Model):
    """Finansal ve kredi profili."""

    driver = models.OneToOneField(
        "api.Driver",
        on_delete=models.CASCADE,
        related_name="financial_profile",
    )
    findeks_score = models.PositiveSmallIntegerField(null=True, blank=True)
    credit_debt_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    has_enforcement_record = models.BooleanField(default=False)
    bank_blacklist_flag = models.BooleanField(default=False)
    payment_delay_count = models.PositiveSmallIntegerField(default=0)
    fraud_suspicion = models.BooleanField(default=False)
    reference_status = models.CharField(max_length=32, blank=True, default="")
    findeks_checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("customer financial profile")
        verbose_name_plural = _("customer financial profiles")


class CustomerRentalHistoryStats(models.Model):
    """Kiralama geçmişi özet istatistikleri."""

    driver = models.OneToOneField(
        "api.Driver",
        on_delete=models.CASCADE,
        related_name="rental_history_stats",
    )
    total_rentals = models.PositiveIntegerField(default=0)
    cancelled_count = models.PositiveIntegerField(default=0)
    damaged_return_count = models.PositiveIntegerField(default=0)
    accident_count = models.PositiveIntegerField(default=0)
    late_return_count = models.PositiveIntegerField(default=0)
    traffic_fine_count = models.PositiveIntegerField(default=0)
    clean_return_streak = models.PositiveIntegerField(default=0)
    insurance_claim_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("customer rental history stats")
        verbose_name_plural = _("customer rental history stats")


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
        verbose_name = _("rule definition")
        verbose_name_plural = _("rule definitions")
        ordering = ("priority", "code")
        constraints = (
            models.UniqueConstraint(
                fields=("rule_set", "code"),
                name="uniq_rule_code_per_set",
            ),
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
        verbose_name = _("rental decision log")
        verbose_name_plural = _("rental decision logs")
        ordering = ("created_at",)


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
        verbose_name = _("vehicle risk tier")
        verbose_name_plural = _("vehicle risk tiers")
