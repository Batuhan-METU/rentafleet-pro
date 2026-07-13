"""Eşleşen piyasa fiyatları için özet istatistikler."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceStatistics:
    min_price: float
    average_price: float
    max_price: float


def calculate_statistics(daily_prices: list[float]) -> PriceStatistics | None:
    """Minimum, ortalama ve maksimum günlük fiyat."""
    if not daily_prices:
        return None
    return PriceStatistics(
        min_price=round(min(daily_prices), 2),
        average_price=round(sum(daily_prices) / len(daily_prices), 2),
        max_price=round(max(daily_prices), 2),
    )


def statistics_to_dict(stats: PriceStatistics | None) -> dict | None:
    if stats is None:
        return None
    return {
        "minPrice": stats.min_price,
        "averagePrice": stats.average_price,
        "maxPrice": stats.max_price,
    }