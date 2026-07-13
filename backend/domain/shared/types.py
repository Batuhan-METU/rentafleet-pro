"""Domain value objects ve motor sonuç tipleri."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from backend.domain.shared.enums import RuleEffect


@dataclass(frozen=True)
class CustomerSnapshot:
    """Risk motoru girdisi — ORM'den türetilir."""

    customer_id: int
    company_id: int
    national_id: str
    age: int
    license_age_years: float
    license_points: int
    license_penalty_count: int
    monthly_income: Decimal | None
    findeks_score: int | None
    has_enforcement_record: bool
    bank_blacklist_flag: bool
    payment_delay_count: int
    fraud_suspicion: bool
    identity_verified: bool
    phone_verified: bool
    email_verified: bool
    document_fraud_suspicion: bool
    is_blacklisted: bool
    is_whitelisted: bool
    vip_tier: str
    loyalty_level: int
    total_rentals: int
    cancelled_count: int
    damaged_return_count: int
    accident_count: int
    late_return_count: int
    traffic_fine_count: int
    is_first_rental: bool


@dataclass(frozen=True)
class RuleOutcome:
    code: str
    effect: RuleEffect
    points: int
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineResult:
    engine: str
    score: int | None
    level: str | None
    outcomes: tuple[RuleOutcome, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class EvaluateRentalResult:
    application_id: int
    risk: EngineResult
    approved: bool
    recommended_vehicle_ids: tuple[int, ...] = ()
    vehicles: tuple[dict[str, Any], ...] = ()
    quote: dict[str, Any] | None = None