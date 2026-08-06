"""Domain testleri için ortak CustomerSnapshot fabrikası."""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Any

from backend.domain.shared.types import CustomerSnapshot


def make_snapshot(**overrides: Any) -> CustomerSnapshot:
    """Temiz-geçmişli, düşük riskli varsayılan bir müşteri anlık görüntüsü.

    Testler yalnızca ilgili alanları ``overrides`` ile geçersiz kılar; böylece
    her testte ``CustomerSnapshot``'ın tüm alanlarını tekrar yazmak zorunda
    kalınmaz. ``dataclasses.replace`` kullanılır — ``CustomerSnapshot``
    frozen bir dataclass olduğu için hem doğru tip denetimi sağlar hem de
    "önce oluştur, sonra geçersiz kıl" desenini tek satırda ifade eder.
    """
    base = CustomerSnapshot(
        customer_id=1,
        company_id=1,
        national_id="11111111110",
        age=35,
        license_age_years=10.0,
        license_points=0,
        license_penalty_count=0,
        monthly_income=Decimal("40000"),
        findeks_score=750,
        has_enforcement_record=False,
        bank_blacklist_flag=False,
        payment_delay_count=0,
        fraud_suspicion=False,
        identity_verified=True,
        phone_verified=True,
        email_verified=True,
        document_fraud_suspicion=False,
        is_blacklisted=False,
        is_whitelisted=False,
        vip_tier="NONE",
        loyalty_level=0,
        total_rentals=5,
        cancelled_count=0,
        damaged_return_count=0,
        accident_count=0,
        late_return_count=0,
        traffic_fine_count=0,
        is_first_rental=False,
    )
    return dataclasses.replace(base, **overrides)
