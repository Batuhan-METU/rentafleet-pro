"""Operasyon gideri — MALIYET_HESAPLAMA_METODOLOJISI §3.5.

Bakım, lastik, hasar, yakıt gibi doğrudan araca ve tarihe bağlı giderler —
kredi/genel gider gibi ağırlıklı dağıtıma HİÇ gerek yoktur; mevcut
``VehicleExpense`` kayıtları olduğu gibi toplanır. Bu bileşende "kayıt yok"
gerçekten "sıfır gider" anlamına gelir (§3.3/§3.4'ün aksine burada eksik
konfigürasyon değil, fiilen gerçekleşmemiş işlem söz konusu) — bu yüzden
diğer servislerin aksine ``None`` değil ``Decimal("0")`` döner.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Sum

from backend.apps.vehicle_finance.models import VehicleExpense
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def total_operating_expense_for_vehicle(vehicle: Vehicle, as_of: date | None = None) -> Decimal:
    """§3.5 — aracın tüm işlem kayıtlarının net tutar toplamı."""
    qs = VehicleExpense.objects.filter(vehicle=vehicle)
    if as_of is not None:
        qs = qs.filter(expense_date__lte=as_of)
    total = qs.aggregate(total=Sum("amount"))["total"]
    return _round(Decimal(total)) if total is not None else Decimal("0")


def total_operating_income_for_vehicle(vehicle: Vehicle, as_of: date | None = None) -> Decimal:
    """§3.5 ekine — operasyon gider kayıtlarına bağlı geri kazanım/tahsilat
    (``VehicleExpense.income_amount``) toplamı, ör. sigorta tazminatı.
    Kiralama gelirinden (``RentalIncome``) TAMAMEN AYRI bir kavramdır."""
    qs = VehicleExpense.objects.filter(vehicle=vehicle)
    if as_of is not None:
        qs = qs.filter(expense_date__lte=as_of)
    total = qs.aggregate(total=Sum("income_amount"))["total"]
    return _round(Decimal(total)) if total is not None else Decimal("0")


def average_daily_operating_expense(vehicle: Vehicle, as_of: date) -> Decimal | None:
    """§4 — ortalama yöntem: bugüne kadarki toplam / filoya girişten bugüne gün sayısı.

    ``fleet_entry_date`` yoksa günlük ortalama tanımsızdır → ``None``.
    """
    if vehicle.fleet_entry_date is None:
        return None
    total = total_operating_expense_for_vehicle(vehicle, as_of)
    days = (as_of - vehicle.fleet_entry_date).days
    if days <= 0:
        return Decimal("0")
    return _round(total / days)
