"""`refresh_competitor_prices_task` — Celery görevinin orkestrasyon mantığı.

Enuygun'a gerçek ağ çağrısı yapan `sync_fleet_market_prices` sınır noktası
mock'lanır (bu görev bağımsız olarak canlı Celery worker + Redis üzerinden
`worker@...` -> ping/pong ile uçtan uca doğrulandı — bkz. PR notları; burada
YALNIZCA görevin kendi mantığı — şirket döngüsü, hata izolasyonu — test edilir).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.apps.companies.models import Company
from backend.infrastructure.services.enuygun.tasks import refresh_competitor_prices_task

pytestmark = pytest.mark.django_db


def test_task_calls_sync_for_explicit_company_id(company: Company):
    with patch(
        "backend.infrastructure.services.enuygun.tasks.sync_fleet_market_prices"
    ) as mock_sync:
        mock_sync.return_value = {"vehicle_count": 3}

        result = refresh_competitor_prices_task(company_id=company.pk)

        mock_sync.assert_called_once()
        assert mock_sync.call_args.kwargs["company_id"] == company.pk
        assert result == {company.pk: {"vehicle_count": 3}}


def test_task_iterates_all_companies_when_none_specified(company: Company):
    other = Company.objects.create(name="second-co", tax_number="1230001230")

    with patch(
        "backend.infrastructure.services.enuygun.tasks.sync_fleet_market_prices"
    ) as mock_sync:
        mock_sync.return_value = {"vehicle_count": 0}

        result = refresh_competitor_prices_task()

        assert mock_sync.call_count == 2
        assert set(result.keys()) == {company.pk, other.pk}


def test_task_isolates_a_single_company_failure(company: Company):
    other = Company.objects.create(name="failing-co", tax_number="4560004560")

    def side_effect(*, force, window, company_id):
        if company_id == other.pk:
            raise RuntimeError("Enuygun API hatası")
        return {"vehicle_count": 1}

    with patch(
        "backend.infrastructure.services.enuygun.tasks.sync_fleet_market_prices",
        side_effect=side_effect,
    ):
        result = refresh_competitor_prices_task()

    assert result[company.pk] == {"vehicle_count": 1}
    assert result[other.pk] == {"error": True}
