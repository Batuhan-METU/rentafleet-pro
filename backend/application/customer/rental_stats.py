"""Kiralama geçmişi istatistiklerini Rental kayıtlarından senkronize eder."""

from __future__ import annotations

from django.db.models import Count, Q, Sum

from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import CustomerRentalHistoryStats
from backend.apps.floor_pricing.models import RentalIncome
from backend.apps.reservations.models import RentalStatus


def sync_rental_history_stats(driver: Driver) -> CustomerRentalHistoryStats:
    """Driver.rentals ve gelir kayıtlarından özet istatistikleri günceller."""
    stats, _ = CustomerRentalHistoryStats.objects.get_or_create(driver=driver)

    aggregates = driver.rentals.aggregate(
        total=Count("id", filter=Q(status=RentalStatus.COMPLETED)),
        cancelled=Count("id", filter=Q(status=RentalStatus.CANCELLED)),
    )
    stats.total_rentals = aggregates["total"] or 0
    stats.cancelled_count = aggregates["cancelled"] or 0

    late_returns = (
        RentalIncome.objects.filter(
            rental__driver=driver,
            late_fee__gt=0,
        ).aggregate(total=Count("id"))["total"]
        or 0
    )
    stats.late_return_count = late_returns

    if stats.total_rentals >= 30:
        driver.vip_tier = "PLATINUM"
    elif stats.total_rentals >= 20:
        driver.vip_tier = "GOLD"
    elif stats.total_rentals >= 10:
        driver.vip_tier = "SILVER"
    else:
        driver.vip_tier = driver.vip_tier or "NONE"

    driver.loyalty_level = min(stats.total_rentals // 5, 10)
    driver.lifetime_value = (
        RentalIncome.objects.filter(rental__driver=driver).aggregate(
            total=Sum("base_amount")
        )["total"]
        or 0
    )

    stats.save()
    driver.save(update_fields=["vip_tier", "loyalty_level", "lifetime_value", "updated_at"])
    return stats