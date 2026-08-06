"""Kaça kiraya vermeli? — Kurtaran fiyat — MALIYET_HESAPLAMA_METODOLOJISI §6.

RentA-Fleet PRO'nun zaten gerçek kiralama verisi (``Rental``) olduğu
için doküman §7'deki simüle edilmiş doluluk oranı KULLANILMAZ — doluluk
oranı doğrudan gerçek ``Rental`` kayıtlarından hesaplanır.

    Çarpan = (1 + Hedef Kâr Marjı) / Doluluk Oranı
    Kirada Olunan Günün Kurtaran Fiyatı = Güncel Günlük Maliyet × Çarpan

Sabit kâr marjı + değişken doluluk oranı = matematiksel olarak kaçınılmaz
zarar riski (§10 madde 6) — bu yüzden çarpan doluluğa göre düzeltilir,
sabit bırakılmaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from backend.apps.rentals.choices import RentalStatus
from backend.apps.rentals.models import Rental
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.company_settings import (
    get_cost_settings,
)
from backend.infrastructure.services.cost_calculation.day_math import bucket_days_in_range
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES
from backend.infrastructure.services.cost_calculation.total_cost_service import (
    HybridDailyCost,
    build_hybrid_daily_cost,
)

FOUR_PLACES = Decimal("0.0001")

# "Kirada" sayılan durumlar — İPTAL edilen kiralamalar doluluğa dahil edilmez.
_OCCUPIED_STATUSES = (RentalStatus.ACTIVE, RentalStatus.COMPLETED)


def _round2(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _round4(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _rented_days_for_vehicle(vehicle: Vehicle, as_of: date) -> int:
    """Gerçek ``Rental`` kayıtlarından, aracın kirada geçirdiği gün sayısı.

    Hem pickup hem dönüş günü dahil edilir (kova/bucket kuralı, §1.4b) —
    "bu araç bugün kirada mıydı" sorusu, "içinde bulunma" tipi bir sorgudur.
    Hâlâ aktif ve fiilen teslim alınmamış kiralamalar ``as_of``'a kadar
    kirada kabul edilir.
    """
    # Tek çağıran (real_occupancy_rate) fleet_entry_date=None ise buraya hiç
    # gelmez (erken döner) — bu invariant'ı açıkça doğrular.
    assert vehicle.fleet_entry_date is not None
    entry_date = vehicle.fleet_entry_date
    rentals = Rental.objects.filter(vehicle=vehicle, status__in=_OCCUPIED_STATUSES)
    total = 0
    for rental in rentals:
        start = rental.started_at.date()
        end_dt = rental.actual_return_at or rental.ended_at
        end = end_dt.date() if end_dt else as_of
        total += bucket_days_in_range(start, end, entry_date=entry_date, as_of=as_of)
    return total


def real_occupancy_rate(vehicle: Vehicle, as_of: date) -> Decimal | None:
    """§6 — gerçek doluluk oranı: kirada geçen gün / filoya girişten bugüne toplam gün.

    ``fleet_entry_date`` yoksa ya da filo süresi 0/negatifse ``None`` döner.
    """
    if vehicle.fleet_entry_date is None:
        return None
    total_days = (as_of - vehicle.fleet_entry_date).days + 1
    if total_days <= 0:
        return None
    rented_days = _rented_days_for_vehicle(vehicle, as_of)
    return _round4(Decimal(rented_days) / Decimal(total_days))


@dataclass
class FloorPriceResult:
    """§6 — kurtaran fiyat sonucu, şeffaflık için tüm ara değerlerle."""

    daily_cost: Decimal | None
    occupancy_rate: Decimal | None
    target_profit_margin: Decimal | None
    multiplier: Decimal | None
    daily_floor_price: Decimal | None
    missing_components: list[str]
    message: str


def build_floor_price(vehicle: Vehicle, as_of: date | None = None) -> FloorPriceResult:
    """§6 — hibrit günlük maliyeti, doluluk-düzeltmeli çarpanla kurtaran fiyata çevirir."""
    as_of = as_of or date.today()
    hybrid: HybridDailyCost = build_hybrid_daily_cost(vehicle, as_of)

    if hybrid.total_daily is None:
        return FloorPriceResult(
            daily_cost=None,
            occupancy_rate=None,
            target_profit_margin=None,
            multiplier=None,
            daily_floor_price=None,
            missing_components=hybrid.missing_components,
            message="Maliyet bileşenleri eksik olduğu için kurtaran fiyat hesaplanamadı.",
        )

    occupancy = real_occupancy_rate(vehicle, as_of)
    settings = get_cost_settings(vehicle.company)
    target_margin = Decimal(settings.target_profit_margin)

    if occupancy is None:
        return FloorPriceResult(
            daily_cost=hybrid.total_daily,
            occupancy_rate=None,
            target_profit_margin=target_margin,
            multiplier=None,
            daily_floor_price=None,
            missing_components=["fleet_entry_date"],
            message="Filoya giriş tarihi olmadığı için doluluk oranı hesaplanamadı.",
        )

    if occupancy <= 0:
        return FloorPriceResult(
            daily_cost=hybrid.total_daily,
            occupancy_rate=occupancy,
            target_profit_margin=target_margin,
            multiplier=None,
            daily_floor_price=None,
            missing_components=["occupancy_rate"],
            message="Gerçek kiralama kaydı olmadığı için doluluk oranı sıfır — kurtaran fiyat tanımsız.",
        )

    multiplier = (Decimal(1) + target_margin) / occupancy
    floor_price = _round2(hybrid.total_daily * multiplier)

    return FloorPriceResult(
        daily_cost=hybrid.total_daily,
        occupancy_rate=occupancy,
        target_profit_margin=target_margin,
        multiplier=_round4(multiplier),
        daily_floor_price=floor_price,
        missing_components=[],
        message=(
            f"Günlük maliyet {hybrid.total_daily} TL, %{occupancy * 100:.1f} doluluk "
            f"ve %{target_margin * 100:.0f} hedef kâr ile kurtaran fiyat {floor_price} TL/gün."
        ),
    )
