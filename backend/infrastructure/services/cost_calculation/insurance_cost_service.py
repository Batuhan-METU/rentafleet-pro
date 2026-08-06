"""Sigorta / kasko maliyeti — MALIYET_HESAPLAMA_METODOLOJISI §3.4.

Her poliçe tek bir araca aittir, havuzlu dağıtım YOKTUR. Bir araç birden
fazla poliçe TİPİNE (Trafik + Kasko + Yeşil Kart) sahip olabilir — bunların
toplamı aracın sigorta maliyetidir. Süresi dolmuş ama yeni kaydı henüz
girilmemiş bir poliçe, "aynı günlük oranla yenilenmiş" varsayılır (§3.4) —
sigorta maliyeti aniden sıfıra düşmez.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from backend.apps.vehicle_finance.models import InsurancePolicy
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.day_math import period_days
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES

DAYS_PER_YEAR = Decimal(365)


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _daily_rate(policy: InsurancePolicy) -> Decimal:
    return Decimal(policy.amount) / DAYS_PER_YEAR


def _policies_by_type(vehicle: Vehicle) -> dict[str, list[InsurancePolicy]]:
    grouped: dict[str, list[InsurancePolicy]] = {}
    for policy in InsurancePolicy.objects.filter(vehicle=vehicle).order_by("start_date"):
        grouped.setdefault(policy.policy_type, []).append(policy)
    return grouped


def accrued_insurance_for_vehicle(vehicle: Vehicle, as_of: date) -> Decimal | None:
    """§3.4 — her poliçe tipi için tahakkuk toplamı; hiç poliçe yoksa ``None``.

    Bilinen son poliçenin bitişinden sonrası, yeni poliçe girilene kadar
    aynı günlük oranla "yenilenmiş" kabul edilerek tahakkuk etmeye devam
    eder (§3.4 — "sigorta maliyeti aniden sıfıra düşmez").
    """
    by_type = _policies_by_type(vehicle)
    if not by_type:
        return None

    total = Decimal("0")
    for policies in by_type.values():
        for policy in policies:
            if policy.start_date > as_of:
                continue
            accrual_end = min(policy.end_date, as_of)
            total += _daily_rate(policy) * period_days(policy.start_date, accrual_end)

        last_policy = policies[-1]
        if as_of > last_policy.end_date:
            total += _daily_rate(last_policy) * period_days(last_policy.end_date, as_of)

    return _round(total)


def current_daily_insurance_rate(vehicle: Vehicle, as_of: date) -> Decimal | None:
    """§4 — marjinal/güncel oran: her poliçe tipi için en güncel (start<=as_of) poliçenin günlük oranı.

    Poliçenin süresi dolmuş olması bu oranı değiştirmez (yenilenme
    varsayımı) — yalnızca daha yeni bir poliçe girildiğinde oran güncellenir.
    """
    by_type = _policies_by_type(vehicle)
    if not by_type:
        return None

    total = Decimal("0")
    for policies in by_type.values():
        current = [p for p in policies if p.start_date <= as_of]
        if not current:
            continue
        latest = max(current, key=lambda p: p.start_date)
        total += _daily_rate(latest)

    return _round(total)
