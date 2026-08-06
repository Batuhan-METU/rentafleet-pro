"""GET /api/fleet/overview/ — yıllık KPI hesabının kısa süreli (60 sn) Redis/
LocMemCache önbelleğe alındığını doğrular (bkz. company_overview_service).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import RentalIncome
from backend.apps.vehicles.models import Vehicle, VehicleStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_overview_year_metrics_second_call_is_served_from_cache(client, company: Company):
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="34OVR001",
        brand="Renault",
        model="Clio",
        production_year=2023,
        current_km=5000,
        status=VehicleStatus.AVAILABLE,
    )
    RentalIncome.objects.create(
        vehicle=vehicle,
        start_date=date.today() - timedelta(days=10),
        end_date=date.today() - timedelta(days=5),
        base_amount=Decimal("5000"),
    )

    first = client.get("/api/fleet/overview/")
    assert first.status_code == 200

    with CaptureQueriesContext(connection) as ctx:
        second = client.get("/api/fleet/overview/")
    assert second.status_code == 200
    assert second.data["istatistikler"] == first.data["istatistikler"]

    # İkinci çağrıda YILLIK METRİKLER için hiçbir RentalIncome/VehicleExpense
    # sorgusu ÇALIŞMAMALI — önbellekten gelmeli. (Filo durumu/branding gibi
    # canlı kalması gereken diğer alanlar hâlâ sorgulanır, bu yüzden toplam
    # sorgu sayısı sıfır değil ama gelir/gider sorgusu YOK.)
    executed_sql = " ".join(q["sql"] for q in ctx.captured_queries)
    assert "vehicle_finance_rentalincome" not in executed_sql.lower()
