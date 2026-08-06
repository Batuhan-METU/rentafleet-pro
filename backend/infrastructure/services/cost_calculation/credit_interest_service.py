"""Kredi faizi — MALIYET_HESAPLAMA_METODOLOJISI §3.1.

İki aşama:
  1. ``generate_amortization_schedule`` — bir ``Loan``'ın azalan bakiyeli
     amortisman tablosunu (``LoanInstallment`` satırları) üretip precompute
     eder.
  2. ``distribute_loan_costs`` / ``accrued_credit_cost_for_vehicle`` — bir
     kredinin taksitlerini, o krediye bağlı TÜM araçlara gün×tutar
     ağırlıklı olarak dağıtır.

Formüller dokümandan birebir alınmıştır; sadeleştirme yapılmamıştır
(BSMV'nin anaparadan düşülmesi ve son taksitte yuvarlama düzeltmesi dahil).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

from django.db import transaction
from django.db.models import Sum

from backend.apps.vehicle_finance.models import Loan, LoanInstallment
from backend.infrastructure.services.cost_calculation.company_settings import (
    get_cost_settings,
)
from backend.infrastructure.services.cost_calculation.day_math import (
    add_months,
    period_days,
)
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _loan_bsmv_rate(loan: Loan) -> Decimal:
    if loan.bsmv_rate is not None:
        return Decimal(loan.bsmv_rate)
    return Decimal(get_cost_settings(loan.company).bsmv_rate)


def _fixed_installment_amount(principal: Decimal, monthly_rate: Decimal, term_months: int) -> Decimal:
    """§3.1 Adım 1 — Sabit Taksit Tutarı = P × r / (1 − (1+r)^−n)."""
    if monthly_rate == 0:
        return _round(principal / term_months)
    factor = Decimal(1) - (Decimal(1) + monthly_rate) ** (-term_months)
    return _round(principal * monthly_rate / factor)


def _installment_rows(loan: Loan) -> list[dict]:
    principal = Decimal(loan.principal_amount)
    rate = Decimal(loan.monthly_interest_rate)
    n = int(loan.term_months)
    bsmv_rate = _loan_bsmv_rate(loan)
    fixed_payment = _fixed_installment_amount(principal, rate, n)

    remaining = principal
    rows: list[dict] = []
    for i in range(1, n + 1):
        interest = _round(remaining * rate)
        bsmv = _round(interest * bsmv_rate)
        if i < n:
            principal_amt = _round(fixed_payment - interest - bsmv)
            total = fixed_payment
        else:
            # Son taksit: kalan anapara tam kapatılır, taksit tutarı buna
            # göre yeniden hesaplanır (doc §3.1 — aksi halde kalan anapara
            # BSMV'nin anaparadan düşmesi yüzünden asla tam sıfıra inmez).
            principal_amt = remaining
            total = _round(principal_amt + interest + bsmv)
        remaining = remaining - principal_amt
        rows.append(
            {
                "installment_no": i,
                "due_date": add_months(loan.start_date, i),
                "total_amount": total,
                "principal_amount": _round(principal_amt),
                "interest_amount": interest,
                "bsmv_amount": bsmv,
                "remaining_principal_after": _round(remaining),
            }
        )
    return rows


@transaction.atomic
def generate_amortization_schedule(loan: Loan) -> list[LoanInstallment]:
    """Loan parametrelerinden taksit tablosunu üretir ve DB'ye yazar.

    İdempotent: mevcut taksitler silinip yeniden üretilir — kredi
    parametreleri değiştiğinde (principal/rate/term/start_date) bu
    fonksiyon yeniden çağrılmalıdır.
    """
    rows = _installment_rows(loan)
    LoanInstallment.objects.filter(loan=loan).delete()
    LoanInstallment.objects.bulk_create(
        LoanInstallment(loan=loan, **row) for row in rows
    )
    return list(loan.installments.order_by("installment_no"))


class VehicleLoanShare(TypedDict):
    accrued: Decimal
    # Sadece bu krediye ait bir SONRAKİ taksit yoksa (ör. kredi zaten
    # kapanmış) None olur — "accrued"tan farklı olarak gerçekten opsiyonel.
    next_installment_daily: Decimal | None


@dataclass
class LoanDistributionResult:
    """Bir kredinin araçlara dağıtım sonucu."""

    per_vehicle: dict[int, VehicleLoanShare] = field(default_factory=dict)
    undistributed_amount: Decimal = Decimal("0")


def distribute_loan_costs(loan: Loan, as_of: date) -> LoanDistributionResult:
    """§3.1 Adım 2 — kredinin TÜM taksit dönemlerini ilişkili araçlara dağıtır.

    Loan seviyesinde TEK GEÇİŞTE çalışır (araç başına ayrı sorgu yok —
    dokümanın N+1 uyarısına uygun). Her taksit dönemi için ağırlık =
    ``financed_amount × dönem_gün_sayısı`` (§1.4a kuralı, aracın
    ``fleet_entry_date``'i ile kırpılır). ``fleet_entry_date``'i olmayan
    araçlara pay verilmez (§1.5 — Bilinmiyor ≠ Sıfır, sessizce dahil
    edilmez).

    Dönen ``per_vehicle[vehicle_id]``:
      * ``accrued`` — ``due_date <= as_of`` olan taksitlerden bu araca
        düşen toplam pay (anapara+faiz+BSMV, doc'un "taksit tutarı"
        tanımıyla).
      * ``next_installment_daily`` — ``as_of``'tan sonraki İLK taksitin bu
        araca düşen payının günlüğe bölünmüş hâli (§4 marjinal oran,
        sabit 30 gün varsayımıyla — doc §3.1 Adım 2).
    """
    allocations = list(loan.vehicle_allocations.select_related("vehicle"))
    if not allocations:
        return LoanDistributionResult()

    installments = list(loan.installments.order_by("installment_no"))
    accrued: dict[int, Decimal] = {alloc.vehicle_id: Decimal("0") for alloc in allocations}
    marginal_daily: dict[int, Decimal] = {}
    undistributed = Decimal("0")

    prev_due = loan.start_date
    marginal_found = False
    for installment in installments:
        weights: dict[int, Decimal] = {}
        total_weight = Decimal("0")
        for alloc in allocations:
            entry_date = alloc.vehicle.fleet_entry_date
            if entry_date is None:
                continue
            days = period_days(prev_due, installment.due_date, entry_date)
            if days <= 0:
                continue
            weight = Decimal(alloc.financed_amount) * days
            if weight > 0:
                weights[alloc.vehicle_id] = weight
                total_weight += weight

        if installment.due_date <= as_of:
            if total_weight > 0:
                for vehicle_id, weight in weights.items():
                    accrued[vehicle_id] += (weight / total_weight) * Decimal(installment.total_amount)
            else:
                undistributed += Decimal(installment.total_amount)
        elif not marginal_found:
            marginal_found = True
            if total_weight > 0:
                for vehicle_id, weight in weights.items():
                    share = (weight / total_weight) * Decimal(installment.total_amount)
                    marginal_daily[vehicle_id] = share / Decimal(30)

        prev_due = installment.due_date

    per_vehicle: dict[int, VehicleLoanShare] = {
        vehicle_id: VehicleLoanShare(
            accrued=_round(total),
            next_installment_daily=(
                _round(marginal_daily[vehicle_id]) if vehicle_id in marginal_daily else None
            ),
        )
        for vehicle_id, total in accrued.items()
    }
    return LoanDistributionResult(per_vehicle=per_vehicle, undistributed_amount=_round(undistributed))


def accrued_credit_cost_for_vehicle(vehicle, as_of: date) -> dict[str, Decimal] | None:
    """Tek araç için bugüne kadarki kredi tahakkuku + güncel marjinal günlük oran.

    Aracın bağlı olduğu kredi yoksa ``None`` döner (§1.5 — finansmanı
    Kredi/Karma olmayan ya da hiç kredisi olmayan araç için kredi bileşeni
    'yok' anlamına gelir, 0 değil). Filo geneli toplu hesap için (birden
    fazla araç aynı krediyi paylaşıyorsa N+1'den kaçınmak amacıyla)
    ``distribute_loan_costs``'u doğrudan loan bazında kullanın.
    """
    loans = Loan.objects.filter(vehicle_allocations__vehicle=vehicle).distinct()
    if not loans.exists():
        return None

    accrued_total = Decimal("0")
    marginal_daily_total = Decimal("0")
    for loan in loans:
        result = distribute_loan_costs(loan, as_of)
        data = result.per_vehicle.get(vehicle.id)
        if data:
            accrued_total += data["accrued"]
            marginal_daily_total += data["next_installment_daily"] or Decimal("0")

    return {"accrued": _round(accrued_total), "marginal_daily": _round(marginal_daily_total)}


def validate_loan_distribution(loan: Loan, tolerance: Decimal = Decimal("0.05")) -> dict:
    """§10 madde 5 — dağıtılan toplam == taksit toplamına eşit mi.

    Doğrulama TÜM vade boyunca yapılır (``as_of`` = son taksit tarihi),
    sadece bugüne kadarki kısım değil — aksi halde henüz vadesi
    gelmemiş taksitler karşılaştırma dışı kalır.
    """
    last_due = loan.installments.order_by("-due_date").values_list("due_date", flat=True).first()
    if last_due is None:
        return {
            "is_valid": True,
            "message": "Taksit planı henüz üretilmemiş.",
            "difference": Decimal("0"),
        }

    result = distribute_loan_costs(loan, as_of=last_due)
    distributed_total = sum(
        (v["accrued"] for v in result.per_vehicle.values()), Decimal("0")
    ) + result.undistributed_amount
    installment_total = loan.installments.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
    diff = abs(distributed_total - installment_total)

    return {
        "is_valid": diff <= tolerance,
        "distributed_total": distributed_total,
        "installment_total": installment_total,
        "difference": diff,
        "undistributed_amount": result.undistributed_amount,
    }
