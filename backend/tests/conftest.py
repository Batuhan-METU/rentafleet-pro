"""Paylaşılan pytest fixture'ları.

`company`/`manager`/`client` neredeyse birebir aynı haliyle 19+ test
dosyasında kopyalanmıştı (bkz. denetim raporu — "fixture duplication").
Bu üçü tamamen jenerik boilerplate'tir: hiçbir test `company.name`,
`tax_number` veya `manager`'ın `username`'ine göre assert yapmıyor —
sadece benzersiz bir şirket/kullanıcı olmaları yeterli. Buraya taşınmaları
davranışı DEĞİŞTİRMEZ, sadece 19 kopyayı tek kaynağa indirir.

Bilerek BURAYA TAŞINMAYANLAR: `driver`/`vehicle` fixture'ları — bu ikisi
dosyadan dosyaya plaka/marka/risk profili gibi gerçekten testin mantığına
etki eden farklı değerler kullanıyor, tek bir jenerik fixture'a
indirgenirse test senaryoları arasındaki kasıtlı farklar kaybolur.
`test_maintenance_export.py`/`test_rental_export.py`/`test_fleet_export.py`
kendi `client`/`staff` fixture'larını KORUR — onlar bilerek FLEET_MANAGER
değil OPERATIONS_STAFF rolüyle test ediyor, bu jenerik `client`'a dahil
edilemez.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from backend.apps.companies.choices import UserRole
from backend.apps.companies.models import Company, CustomUser


@pytest.fixture
def company() -> Company:
    return Company.objects.create(name="test-tenant", tax_number="0000000001")


@pytest.fixture
def manager(company: Company) -> CustomUser:
    return CustomUser.objects.create_user(
        username="test_manager",
        password="test-pass-123",
        company=company,
        role=UserRole.FLEET_MANAGER,
    )


@pytest.fixture
def client(manager: CustomUser) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=manager)
    return api_client
