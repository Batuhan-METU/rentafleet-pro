"""`_naive_utc` — gerçek çalışma zamanı hatası regresyon testi.

``django.utils.timezone.utc`` Django 5'te kaldırıldı; bu fonksiyon aware bir
datetime ile çağrıldığında ``AttributeError`` fırlatıyordu (hiçbir test aware
bir değerle çağırmadığı için fark edilmemişti — bkz. mypy denetimi)."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.infrastructure.services.analytics.scoring_service import _naive_utc


def test_naive_utc_strips_tzinfo_from_aware_datetime():
    aware = datetime(2026, 3, 15, 9, 30, tzinfo=UTC)

    result = _naive_utc(aware)

    assert result.tzinfo is None
    assert result == datetime(2026, 3, 15, 9, 30)


def test_naive_utc_leaves_naive_datetime_unchanged():
    naive = datetime(2026, 3, 15, 9, 30)

    result = _naive_utc(naive)

    assert result == naive
    assert result.tzinfo is None
