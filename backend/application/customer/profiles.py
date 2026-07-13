"""Müşteri profil güncelleme yardımcıları."""

from __future__ import annotations

from backend.apps.customer_profiles.models import Driver


def apply_customer_profiles(driver: Driver, data: dict) -> None:
    """identity / license / financial sözlüklerini ORM profillerine yazar."""
    if identity := data.get("identity"):
        for key, value in identity.items():
            setattr(driver.identity_profile, key, value)
        driver.identity_profile.save()
    if license_data := data.get("license"):
        for key, value in license_data.items():
            setattr(driver.license_profile, key, value)
        driver.license_profile.save()
    if financial := data.get("financial"):
        for key, value in financial.items():
            setattr(driver.financial_profile, key, value)
        driver.financial_profile.save()