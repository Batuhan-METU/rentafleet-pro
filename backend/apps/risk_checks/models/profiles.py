"""Müşteri profil modelleri (kimlik, ehliyet, finans, kiralama geçmişi)."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


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
        app_label = "api"
        db_table = "api_customeridentityprofile"
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
        app_label = "api"
        db_table = "api_customerlicenseprofile"
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
        app_label = "api"
        db_table = "api_customerfinancialprofile"
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
        app_label = "api"
        db_table = "api_customerrentalhistorystats"
        verbose_name = _("customer rental history stats")
        verbose_name_plural = _("customer rental history stats")
