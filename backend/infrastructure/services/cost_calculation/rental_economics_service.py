"""Kiralama fiyat ekonomisi (RentA-Fleet PRO) — v2.

MALIYET_HESAPLAMA_METODOLOJISI'ndeki gerçek maliyet motorunu
(``backend.infrastructure.services.cost_calculation``) filo müdürü
ekranlarına bağlayan façade modül. Eski naif "yıllık yük / 365" formülü
(v1) TAMAMEN kaldırılmıştır — artık kredi/nakit fırsat/genel gider/sigorta/
operasyon bileşenlerinin gerçek tahakkukuna (§3), hibrit güncel günlük
maliyete (§4) ve doluluk-düzeltmeli kurtaran fiyata (§6) dayanır.

Bu modül, ``rental_economics_service`` adının önceden diğer servislerde
(``return_processing``, ``fleet_export_service``, ``company_overview_service``,
``vehicles/serializers``) referans alınan tek "fiyatlama façade'i" olma
rolünü korur — o modüller burada tanımlı ``current_daily_cost`` /
``build_vehicle_profit_summary`` / ``build_cost_analysis_payload``'ı
çağırmaya devam eder, içeride artık yeni motoru kullanırlar.

Piyasa karşılaştırması (``CompetitorPrice``) ve müdür teklifi kâr analizi
mantığı v1'den değişmeden korunmuştur — bunlar maliyet hesabından bağımsız.

Not (isimlendirme): bu dosyadaki fonksiyon/sınıf/yerel değişken isimleri
İngilizceleştirilmiştir. API yanıtı olarak döndürülen dict'lerin KEY'LERİ
de (İsimlendirme Temizliği Faz 3 — floor_pricing) İngilizceleştirilmiştir;
bu değişiklik ilgili Vue bileşenleriyle eş zamanlı yapılmıştır.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from backend.apps.enuygun.models import CompetitorPrice
from backend.apps.vehicle_finance.models import RentalIncome
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.common.date_helper import rental_window
from backend.infrastructure.services.cost_calculation.floor_price_service import (
    FloorPriceResult,
    build_floor_price,
)
from backend.infrastructure.services.cost_calculation.operating_expense_service import (
    total_operating_income_for_vehicle,
)
from backend.infrastructure.services.cost_calculation.total_cost_service import (
    CostBreakdown,
    HybridDailyCost,
    build_cost_breakdown,
    build_cost_breakdown_for_period,
    build_hybrid_daily_cost,
)

# Eksik bileşen kodu → filo müdürüne gösterilecek Türkçe açıklama.
MISSING_COMPONENT_LABELS: dict[str, str] = {
    "fleet_entry_date": "Aracın filoya giriş tarihi girilmemiş.",
    "financing_profile": "Aracın finansal profili (satın alma/finansman) girilmemiş.",
    "credit_allocation": "Finansman tipi Kredi/Karma ama araca bağlı kredi tahsisi girilmemiş.",
    "cash_amount": "Finansman tipi Nakit/Karma ama nakit finanse edilen tutar girilmemiş.",
    "overhead": "Şirketin genel gider verisi (personel/kira/elektrik) henüz girilmemiş.",
    "insurance": "Aracın sigorta/kasko poliçesi girilmemiş.",
    "operating": "Operasyon gideri ortalaması hesaplanamadı.",
    "occupancy_rate": "Gerçek kiralama kaydı olmadığı için doluluk oranı hesaplanamadı.",
}


@dataclass(frozen=True)
class CompetitorQuote:
    """Tek bir rakip kaynağın günlük fiyat satırı."""

    source: str
    daily_price: float


def _f(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def rental_days_between(pickup: date, dropoff: date) -> int:
    """Kiralama gün sayısı (en az 1)."""
    return max((dropoff - pickup).days, 1)


def competitor_quotes_for_vehicle(
    vehicle_id: int,
    *,
    pickup_date: date | None = None,
    dropoff_date: date | None = None,
) -> list[CompetitorQuote]:
    """Belirli araç ve tarih penceresi için DB'deki rakip günlük fiyatları."""
    window = rental_window()
    pickup = pickup_date or window.pickup_date
    dropoff = dropoff_date or window.dropoff_date
    rows = CompetitorPrice.objects.filter(
        vehicle_id=vehicle_id,
        pickup_date=pickup,
        dropoff_date=dropoff,
    ).order_by("source_name")
    return [
        CompetitorQuote(source=row.source_name, daily_price=float(row.daily_price))
        for row in rows
    ]


def current_daily_cost(vehicle: Vehicle, as_of: date | None = None) -> Decimal | None:
    """§4 — hibrit güncel günlük maliyet. Diğer servislerin ortak giriş noktası.

    Veri eksikse (fleet_entry_date, finansman profili, sigorta, genel gider
    bileşenlerinden biri uygulanabilir olduğu hâlde eksikse) ``None`` döner
    — §1.5 gereği asla sessizce 0 sayılmaz.
    """
    return build_hybrid_daily_cost(vehicle, as_of or date.today()).total_daily


def build_vehicle_profit_summary(vehicle: Vehicle, as_of: date | None = None) -> dict:
    """Tamamlanan kiralamalardan biriken net kâr (gelir − güncel günlük maliyet × gün)."""
    as_of = as_of or date.today()
    daily = current_daily_cost(vehicle, as_of)

    # Filo geneli dışa aktarım gibi bir seferde ÇOK araç için çağrılan
    # yerler `Prefetch("incomes", ..., to_attr="prefetched_incomes")` ile
    # önceden yükleyip N+1'i önleyebilir (bkz. apps/vehicles/views.py
    # VehicleExportView) — önbellek yoksa (tekil araç) eskisi gibi sorgulanır.
    prefetched = getattr(vehicle, "prefetched_incomes", None)
    incomes = prefetched if prefetched is not None else list(
        RentalIncome.objects.filter(vehicle=vehicle).order_by("-start_date")
    )
    total_revenue = sum(_f(inc.total_income) for inc in incomes)
    rented_days = sum(inc.total_days for inc in incomes)

    if daily is None:
        return {
            "accumulated_profit": None,
            "total_revenue": round(total_revenue, 2),
            "total_cost": None,
            "rental_count": len(incomes),
            "rented_days": rented_days,
            "avg_profit_per_day": None,
        }

    total_cost = float(daily) * rented_days
    total_profit = total_revenue - total_cost
    return {
        "accumulated_profit": round(total_profit, 2),
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "rental_count": len(incomes),
        "rented_days": rented_days,
        "avg_profit_per_day": round(total_profit / rented_days, 2) if rented_days > 0 else None,
    }


def build_cost_breakdown_payload(breakdown: CostBreakdown) -> dict:
    """§3.6 — Genel Toplam Maliyet, 5 bileşen ayrı ayrı (matematik dokümana birebir)."""
    return {
        "credit_cost": breakdown.credit_cost,
        "cash_opportunity_cost": breakdown.cash_opportunity_cost,
        "cash_opportunity_term_end_date": breakdown.cash_opportunity_term_end_date,
        "overhead_share": breakdown.overhead_share,
        "insurance_cost": breakdown.insurance_cost,
        "operating_expense": breakdown.operating_expense,
        "total_cost": breakdown.total,
    }


def build_missing_fields_payload(missing_components: list[str]) -> list[dict]:
    """Eksik veri bileşenleri — eski 'tahmini_alanlar' sözleşmesiyle aynı şekil.

    v1'de bu alan "varsayılan değerle dolduruldu" anlamına geliyordu; v2'de
    "bu bileşen için gerçek veri eksik, toplam bunu içermiyor" anlamına
    gelir (§1.5) — isim geriye dönük uyumluluk için korunmuştur.
    """
    return [
        {"field": key, "description": MISSING_COMPONENT_LABELS.get(key, key)}
        for key in missing_components
    ]


def build_cost_analysis_payload(vehicle: Vehicle, as_of: date | None = None) -> dict | None:
    """Araç detay/oluşturma yanıtı için özet maliyet kartı (§3.6 + §4).

    Hem toplam hem güncel günlük maliyet hesaplanamıyorsa (temel veri —
    ör. filoya giriş tarihi — tamamen eksikse) ``None`` döner.
    """
    as_of = as_of or date.today()
    breakdown = build_cost_breakdown(vehicle, as_of)
    daily = current_daily_cost(vehicle, as_of)

    if breakdown.total is None and daily is None:
        return None

    return {
        "daily_cost": daily,
        "total_cost": breakdown.total,
        "cost_breakdown": build_cost_breakdown_payload(breakdown),
        "missing_fields": build_missing_fields_payload(breakdown.missing_components),
        "message": (
            f"Güncel günlük maliyet {daily} TL."
            if daily is not None
            else "Güncel günlük maliyet için finansman/sigorta/filoya giriş verisi eksik."
        ),
    }


def build_vehicle_yearly_summary(vehicle: Vehicle, year: int | None = None) -> dict:
    """Araç Detayı 'Gelir & Gider Özeti' — yıla göre gelir/gider/günlük maliyet.

    Ana sayfanın (``company_overview_service``) yıl seçici desenine paralel:
    her yıl için o yılın (içinde bulunduğumuz yıl için bugüne kadarki)
    kira geliri, o yılda tahakkuk eden gider (§3.6, ``build_cost_breakdown_
    for_period`` — iki anlık görüntünün farkı) ve o yılın SONUNDAKİ (ya da
    bugünkü) hibrit günlük maliyet oranı (§4, ``build_hybrid_daily_cost``)
    döner. Hiçbir formül değişmez — sadece hangi tarihe kadar hesaplandığı
    (``as_of``) değişir.
    """
    today = date.today()
    if vehicle.fleet_entry_date is not None:
        available_years = list(range(vehicle.fleet_entry_date.year, today.year + 1))[::-1]
    else:
        available_years = [today.year]

    selected_year = year if year is not None else today.year
    if selected_year not in available_years:
        selected_year = available_years[0]

    year_start = date(selected_year, 1, 1)
    period_end = min(date(selected_year, 12, 31), today)

    incomes = RentalIncome.objects.filter(
        vehicle=vehicle, start_date__gte=year_start, start_date__lte=period_end
    )
    total_income = sum((_f(income.total_income) for income in incomes), 0.0)

    # Operasyon gider kayıtlarına bağlı geri kazanım/tahsilat (ör. sigorta
    # tazminatı) — kiralama gelirinden AYRI bir kaynak, "Gelir Kompozisyonu"
    # kırılımının ikinci segmenti. Aynı iki-anlık-görüntü-farkı deseni
    # (operating_expense ile birebir) — expense_date bazlı, ileri tarihli
    # kayıtlar henüz tahakkuk etmemiş sayılır.
    operating_income = _f(
        total_operating_income_for_vehicle(vehicle, period_end)
        - total_operating_income_for_vehicle(vehicle, year_start - timedelta(days=1))
    )

    breakdown = build_cost_breakdown_for_period(vehicle, year_start, period_end)
    daily = build_hybrid_daily_cost(vehicle, period_end).total_daily

    return {
        "year": selected_year,
        "available_years": available_years,
        "total_income": round(total_income, 2),
        "operating_income": round(operating_income, 2),
        "cost_breakdown": build_cost_breakdown_payload(breakdown),
        "daily_cost": daily,
        "missing_fields": build_missing_fields_payload(breakdown.missing_components),
    }


def build_calculation_steps(
    breakdown: CostBreakdown,
    hybrid: HybridDailyCost,
    floor: FloorPriceResult,
    rental_days: int,
) -> list[dict]:
    """Waterfall adımları — §3.6 → §4 → §6 zincirinin şeffaf dökümü."""
    days = max(int(rental_days), 1)
    period_floor = float(floor.daily_floor_price) * days if floor.daily_floor_price is not None else None

    def _fval(value: Decimal | float | None) -> float | None:
        return float(value) if value is not None else None

    steps = [
        {
            "order": 1,
            "title": "Kredi Faizi (Bugüne Kadar)",
            "description": "Azalan bakiyeli amortisman + BSMV, kredili araçlara gün×tutar ağırlıklı dağıtılmış payı (§3.1).",
            "value": _fval(breakdown.credit_cost),
            "unit": "TL",
            "source_field": "credit_cost",
        },
        {
            "order": 2,
            "title": "Nakit Fırsat Maliyeti (Bugüne Kadar)",
            "description": "Nakit finanse edilen tutarın mevduat faizi eşdeğeri (§3.2).",
            "value": _fval(breakdown.cash_opportunity_cost),
            "unit": "TL",
            "source_field": "cash_opportunity_cost",
        },
        {
            "order": 3,
            "title": "Genel Gider Payı (Bugüne Kadar)",
            "description": "Şirket genel giderlerinden fiyat-ağırlıklı pay (§3.3).",
            "value": _fval(breakdown.overhead_share),
            "unit": "TL",
            "source_field": "overhead_share",
        },
        {
            "order": 4,
            "title": "Sigorta/Kasko Maliyeti (Bugüne Kadar)",
            "description": "Poliçe tahakkuku — süresi dolan poliçe aynı oranla yenilenmiş kabul edilir (§3.4).",
            "value": _fval(breakdown.insurance_cost),
            "unit": "TL",
            "source_field": "insurance_cost",
        },
        {
            "order": 5,
            "title": "Operasyon Gideri (Toplam)",
            "description": "Bakım/lastik/hasar/yakıt gibi araca özel gider kayıtları (§3.5).",
            "value": _fval(breakdown.operating_expense),
            "unit": "TL",
            "source_field": "operating_expense",
        },
        {
            "order": 6,
            "title": "Genel Toplam Maliyet",
            "description": "Yukarıdaki 5 bileşenin toplamı (§3.6).",
            "value": _fval(breakdown.total),
            "unit": "TL",
            "source_field": None,
            "highlighted": True,
        },
        {
            "order": 7,
            "title": "Güncel Günlük Maliyet (Hibrit)",
            "description": "Kredi/Nakit/Sigorta marjinal (güncel oran), Genel Gider/Operasyon ortalama yöntemle (§4).",
            "value": _fval(hybrid.total_daily),
            "unit": "TL/gün",
            "source_field": None,
        },
        {
            "order": 8,
            "title": "Gerçek Doluluk Oranı",
            "description": "Kirada geçen gün / filoya girişten bugüne toplam gün — gerçek kiralama verisinden (§6).",
            "value": _fval(floor.occupancy_rate),
            "unit": "oran",
            "source_field": None,
        },
        {
            "order": 9,
            "title": "Doluluk-Düzeltmeli Çarpan",
            "description": "(1 + hedef kâr marjı) / doluluk oranı (§6).",
            "value": _fval(floor.multiplier),
            "unit": "×",
            "source_field": None,
        },
        {
            "order": 10,
            "title": "Kiralama Süresi",
            "description": "Alış ve dönüş tarihleri arasındaki gün sayısı (en az 1).",
            "value": days,
            "unit": "gün",
            "source_field": None,
        },
        {
            "order": 11,
            "title": "Günlük Kurtaran Fiyat",
            "description": "Güncel günlük maliyet × doluluk-düzeltmeli çarpan (§6) — bu fiyatın altına kiraya vermeyin.",
            "value": _fval(floor.daily_floor_price),
            "unit": "TL/gün",
            "source_field": None,
            "highlighted": True,
        },
        {
            "order": 12,
            "title": "Dönem Kurtaran Fiyatı",
            "description": "Günlük kurtaran fiyat × kiralanan gün.",
            "value": period_floor,
            "unit": "TL",
            "source_field": None,
            "highlighted": True,
        },
    ]
    for step in steps:
        step.setdefault("estimated", False)
    return steps


def build_market_summary_payload(
    competitor_quotes: list[CompetitorQuote],
    rental_days: int,
    *,
    period_floor: float | None = None,
) -> dict:
    """Rakip fiyat özeti — taban fiyatı etkilemez."""
    days = max(int(rental_days), 1)
    prices = [q.daily_price for q in competitor_quotes]
    stats = None
    if prices:
        stats = {
            "min": round(min(prices), 2),
            "avg": round(sum(prices) / len(prices), 2),
            "max": round(max(prices), 2),
        }

    daily_avg = stats["avg"] if stats else None
    period_total = round(daily_avg * days, 2) if daily_avg else None
    warning = None
    if period_total is not None and period_floor is not None and period_total < period_floor:
        warning = (
            f"Dikkat: Piyasa toplamı ({period_total:,.0f} TL) bu dönemin maliyet "
            f"tabanının ({period_floor:,.0f} TL) altında. Bu fiyattan kiralamayın."
        ).replace(",", ".")

    return {
        "does_not_affect_floor": True,
        "quote_count": len(competitor_quotes),
        "daily": stats,
        "period_total": period_total,
        "warning": warning,
        "quotes": [
            {"source": q.source, "daily_price": q.daily_price}
            for q in competitor_quotes
        ],
    }


def build_manager_offer_payload(
    offered_total_price: float,
    period_floor: float,
    rental_days: int,
    *,
    daily_cost: float,
    accumulated_profit: float = 0.0,
    market_summary: dict | None = None,
) -> dict:
    """Müdür teklifi kâr analizi — taban/piyasa matematiği v1'den değişmez."""
    days = max(int(rental_days), 1)
    offered_total = float(offered_total_price)
    profit = round(offered_total - period_floor, 2)
    profit_daily = round(profit / days, 2)
    offered_daily = round(offered_total / days, 2)
    margin_pct = round((profit / offered_total) * 100.0, 1) if offered_total > 0 else None

    market_period_total = (market_summary or {}).get("period_total")
    market_daily_stats = (market_summary or {}).get("daily") or {}
    market_avg_daily = market_daily_stats.get("avg")

    if profit < 0:
        status = "loss"
        status_label = "Tabanın Altında"
        status_message = (
            f"Teklifiniz maliyet tabanının {abs(profit):,.0f} TL altında. "
            "Bu fiyattan kiralama zarar yazar.".replace(",", ".")
        )
    elif profit == 0:
        status = "break_even"
        status_label = "Tam Taban"
        status_message = "Teklifiniz maliyet tabanına eşit; kâr veya zarar yok."
    else:
        status = "profit"
        status_label = "Taban Üstü — Kârlı"
        status_message = (
            f"Teklifiniz tabanın {profit:,.0f} TL üzerinde. "
            f"Günlük kâr: {profit_daily:,.0f} TL.".replace(",", ".")
        )

    market_comparison = None
    market_difference = None
    if market_period_total is not None:
        market_difference = round(offered_total - market_period_total, 2)
        if offered_total < market_period_total:
            market_comparison = "below_market"
        elif offered_total > market_period_total:
            market_comparison = "above_market"
        else:
            market_comparison = "equal_market"

    return {
        "offered_total": offered_total,
        "offered_daily": offered_daily,
        "minimum_floor": period_floor,
        "floor_daily": daily_cost,
        "estimated_profit": profit,
        "estimated_profit_daily": profit_daily,
        "margin_pct": margin_pct,
        "below_floor": profit < 0,
        "difference_from_floor": profit,
        "market_period_total": market_period_total,
        "market_avg_daily": market_avg_daily,
        "market_difference": market_difference,
        "market_comparison": market_comparison,
        "status": status,
        "status_label": status_label,
        "status_message": status_message,
        "accumulated_profit_after": round(accumulated_profit + profit, 2),
    }


def build_pricing_decision_payload(
    vehicle: Vehicle,
    rental_days: int,
    *,
    pickup_date: date | None = None,
    dropoff_date: date | None = None,
    market_daily_average: float | None = None,
    offered_total_price: float | None = None,
) -> dict:
    """Fiyat karar destek ekranı — §3→§4→§6 zincirinin uçtan uca birleşimi."""
    days = max(int(rental_days), 1)
    as_of = date.today()

    breakdown = build_cost_breakdown(vehicle, as_of)
    hybrid = build_hybrid_daily_cost(vehicle, as_of)
    floor = build_floor_price(vehicle, as_of)

    if floor.daily_floor_price is None:
        missing = floor.missing_components or breakdown.missing_components or hybrid.missing_components
        return {
            "has_cost_card": False,
            "message": floor.message or "Maliyet hesaplanamadı.",
            "missing_fields": build_missing_fields_payload(missing),
            "vehicle": {
                "id": vehicle.pk,
                "plate_number": vehicle.plate_number,
                "brand_model": f"{vehicle.brand} {vehicle.model}",
            },
        }

    # `build_floor_price` yalnızca kendi (aynı vehicle/as_of için deterministik)
    # `build_hybrid_daily_cost` çağrısı total_daily=None dönmediğinde bir
    # daily_floor_price üretir (bkz. floor_price_service.py) — yukarıdaki
    # erken dönüşü geçtiysek `hybrid.total_daily` da None OLAMAZ.
    assert hybrid.total_daily is not None
    assert floor.occupancy_rate is not None
    period_floor = round(float(floor.daily_floor_price) * days, 2)
    daily_cost_no_margin = float(hybrid.total_daily)

    competitor_quotes = competitor_quotes_for_vehicle(
        vehicle.pk, pickup_date=pickup_date, dropoff_date=dropoff_date
    )
    if market_daily_average is None and competitor_quotes:
        market_daily_average = sum(q.daily_price for q in competitor_quotes) / len(competitor_quotes)
    market_summary = build_market_summary_payload(competitor_quotes, days, period_floor=period_floor)

    profit_summary = build_vehicle_profit_summary(vehicle, as_of)

    manager_offer = None
    if offered_total_price is not None and offered_total_price > 0:
        manager_offer = build_manager_offer_payload(
            offered_total_price,
            period_floor,
            days,
            daily_cost=daily_cost_no_margin,
            accumulated_profit=profit_summary.get("accumulated_profit") or 0.0,
            market_summary=market_summary,
        )

    message = (
        f"{days} günlük kiralama için kurtaran fiyat {period_floor:,.0f} TL "
        f"(günlük {float(floor.daily_floor_price):,.0f} TL, doluluk "
        f"%{float(floor.occupancy_rate) * 100:.1f})."
    ).replace(",", ".")

    return {
        "has_cost_card": True,
        "vehicle": {
            "id": vehicle.pk,
            "plate_number": vehicle.plate_number,
            "brand_model": f"{vehicle.brand} {vehicle.model}",
            "km": vehicle.current_km,
        },
        "summary": {
            "minimum_floor_price": period_floor,
            "daily_cost": daily_cost_no_margin,
            "daily_floor_price": float(floor.daily_floor_price),
            "occupancy_rate": float(floor.occupancy_rate),
            "rental_days": days,
            "message": message,
        },
        "cost_breakdown": build_cost_breakdown_payload(breakdown),
        "calculation_steps": build_calculation_steps(breakdown, hybrid, floor, days),
        "missing_fields": build_missing_fields_payload(breakdown.missing_components),
        "market": market_summary,
        "manager_offer": manager_offer,
        "profit_history": profit_summary,
        "accumulated_profit": profit_summary.get("accumulated_profit"),
        "rental": {
            "rental_days": days,
            "daily_floor_price": float(floor.daily_floor_price),
            "period_floor_price": period_floor,
        },
        "meta": {
            "calculation_version": "maliyet_hesaplama_metodolojisi_v2",
            "formula_summary": (
                "total_cost = credit + cash_opportunity + overhead + insurance + operating (§3.6); "
                "current_daily = hybrid(marginal credit/cash/insurance + avg overhead/operating) (§4); "
                "floor_price_daily = current_daily × (1+target_profit)/occupancy_rate (§6)"
            ),
            "market_does_not_affect_floor": True,
        },
        "scope_notes": [
            {
                "title": "Doluluk oranı",
                "description": "Gerçek Rental kayıtlarından hesaplanır; simülasyon kullanılmaz.",
            },
            {
                "title": "Finansman",
                "description": "Kredi/Nakit/Karma ayrımı VehicleFinancialProfile ve Loan kayıtlarından gelir.",
            },
            {
                "title": "Eksik veri",
                "description": (
                    "Bir bileşen için veri eksikse toplam 0 değil 'Bilinmiyor' kabul edilir; "
                    "missing_fields listesine bakın."
                ),
            },
        ],
    }
