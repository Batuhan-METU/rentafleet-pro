"""ORM → domain snapshot dönüşümü."""

from __future__ import annotations

from datetime import date

from backend.application.customer.rental_stats import sync_rental_history_stats
from backend.domain.shared.types import CustomerSnapshot
from backend.models import (
    CustomerFinancialProfile,
    CustomerIdentityProfile,
    CustomerLicenseProfile,
    CustomerRentalHistoryStats,
    Driver,
    RentalStatus,
)


def _age_years(birth_date: date) -> int:
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _license_age_years(issue_date: date | None) -> float:
    if issue_date is None:
        return 0.0
    return (date.today() - issue_date).days / 365.25


def ensure_customer_profiles(driver: Driver) -> None:
    CustomerIdentityProfile.objects.get_or_create(driver=driver)
    CustomerLicenseProfile.objects.get_or_create(driver=driver)
    CustomerFinancialProfile.objects.get_or_create(driver=driver)
    CustomerRentalHistoryStats.objects.get_or_create(driver=driver)
    sync_rental_history_stats(driver)


def build_customer_snapshot(driver: Driver, *, is_first_rental: bool | None = None) -> CustomerSnapshot:
    ensure_customer_profiles(driver)
    driver.refresh_from_db()

    identity: CustomerIdentityProfile = driver.identity_profile
    license_p: CustomerLicenseProfile = driver.license_profile
    financial: CustomerFinancialProfile = driver.financial_profile
    stats: CustomerRentalHistoryStats = driver.rental_history_stats

    if is_first_rental is None:
        is_first_rental = driver.rentals.filter(status=RentalStatus.COMPLETED).count() == 0

    return CustomerSnapshot(
        customer_id=driver.pk,
        company_id=driver.company_id,
        national_id=driver.national_id,
        age=_age_years(driver.birth_date),
        license_age_years=_license_age_years(license_p.license_issue_date),
        license_points=license_p.license_points,
        license_penalty_count=license_p.license_penalty_count,
        monthly_income=driver.monthly_income,
        findeks_score=financial.findeks_score,
        has_enforcement_record=financial.has_enforcement_record,
        bank_blacklist_flag=financial.bank_blacklist_flag,
        payment_delay_count=financial.payment_delay_count,
        fraud_suspicion=financial.fraud_suspicion,
        identity_verified=identity.identity_verified,
        phone_verified=identity.phone_verified,
        email_verified=identity.email_verified,
        document_fraud_suspicion=identity.document_fraud_suspicion,
        is_blacklisted=driver.is_blacklisted,
        is_whitelisted=driver.is_whitelisted,
        vip_tier=driver.vip_tier or "NONE",
        loyalty_level=driver.loyalty_level,
        total_rentals=stats.total_rentals,
        cancelled_count=stats.cancelled_count,
        damaged_return_count=stats.damaged_return_count,
        accident_count=stats.accident_count,
        late_return_count=stats.late_return_count,
        traffic_fine_count=stats.traffic_fine_count,
        is_first_rental=is_first_rental,
    )
