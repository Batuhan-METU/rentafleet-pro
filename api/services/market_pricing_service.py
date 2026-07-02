"""Piyasa rakip fiyatlarına dayalı AI fiyat önerisi (RentA-Fleet PRO).

Müdürün girdiği ``CompetitorPrice`` kayıtları ile iç yield motorunun
(``pricing_service``) çıktısını birleştirir; Türkçe ``ai_tavsiyesi`` ve
``gerekce`` üretir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from api.models import CompetitorPrice, Vehicle
from api.services.pricing_service import PricingResult, calculate_suggested_price
from api.services.sipp_service import resolve_sipp

# Piyasa ortalamasının altında kalma hedefi (rekabetçi konum).
MARKET_UNDERCUT_PCT: float = 0.08


@dataclass(frozen=True)
class CompetitorQuote:
    """Tek bir rakip kaynağın fiyat satırı."""

    kaynak: str
    gunluk_fiyat: float


@dataclass(frozen=True)
class MarketPricingAdvice:
    """Piyasa + yield birleşik fiyat önerisi."""

    vehicle_id: int
    onerilen_fiyat: float
    ai_tavsiyesi: str
    gerekce: str
    piyasa_ortalamasi: float | None
    rakip_sayisi: int
    rakipler: list[CompetitorQuote]
    yield_fiyat: float
    yield_gerekce: str
    taban_fiyat: float


def _format_tl(amount: float) -> str:
    """Türkçe binlik ayraçlı TL metni."""
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _vehicle_sipp_code(vehicle: Vehicle) -> str:
    return resolve_sipp(vehicle.brand, vehicle.model, vehicle.sipp_code or None).code


def competitor_quotes_for_vehicle(vehicle_id: int) -> list[CompetitorQuote]:
    rows = CompetitorPrice.objects.filter(vehicle_id=vehicle_id).order_by("source_name")
    return [
        CompetitorQuote(kaynak=row.source_name, gunluk_fiyat=float(row.daily_price))
        for row in rows
    ]


def build_market_pricing_advice(vehicle_id: int) -> MarketPricingAdvice:
    """Rakip fiyatları varsa piyasa ortalamasına göre akıllı öneri üretir."""
    vehicle = Vehicle.objects.select_related("company").get(pk=vehicle_id)
    internal: PricingResult = calculate_suggested_price(vehicle_id)
    rakipler = competitor_quotes_for_vehicle(vehicle_id)

    if not rakipler:
        return MarketPricingAdvice(
            vehicle_id=vehicle_id,
            onerilen_fiyat=internal.final_price,
            ai_tavsiyesi=(
                "Henüz rakip fiyatı girilmedi. Yield motorunun önerdiği fiyatı "
                "kullanabilir veya piyasa fiyatlarını ekleyerek akıllı öneri alabilirsiniz."
            ),
            gerekce=internal.reason,
            piyasa_ortalamasi=None,
            rakip_sayisi=0,
            rakipler=[],
            yield_fiyat=internal.final_price,
            yield_gerekce=internal.reason,
            taban_fiyat=internal.base_price,
        )

    prices = [q.gunluk_fiyat for q in rakipler]
    market_avg = sum(prices) / len(prices)
    smart_price = round(market_avg * (1.0 - MARKET_UNDERCUT_PCT), 2)

    sorted_rakipler = sorted(rakipler, key=lambda q: q.gunluk_fiyat)

    # Yield motoru çok agresif indirim öneriyorsa tabanı koru; aşırı yüksekse
    # piyasa hedefini önceliklendir.
    if smart_price < internal.final_price * 0.75:
        onerilen = round(internal.final_price * 0.95, 2)
        floor_note = (
            " Yield motoru tabanı çok düşük kaldığı için öneri, iç fiyatın "
            f"%5 altı olan {_format_tl(onerilen)} TL seviyesine çekildi."
        )
    else:
        onerilen = smart_price
        floor_note = ""

    undercut_pct = round((1.0 - onerilen / market_avg) * 100, 1) if market_avg else 0.0

    if len(sorted_rakipler) == 1:
        r = sorted_rakipler[0]
        kaynak_ozeti = f"{r.kaynak} ({_format_tl(r.gunluk_fiyat)} TL)"
    elif len(sorted_rakipler) == 2:
        kaynak_ozeti = (
            f"{sorted_rakipler[0].kaynak} ({_format_tl(sorted_rakipler[0].gunluk_fiyat)} TL) ve "
            f"{sorted_rakipler[1].kaynak} ({_format_tl(sorted_rakipler[1].gunluk_fiyat)} TL)"
        )
    else:
        parts = [
            f"{q.kaynak} ({_format_tl(q.gunluk_fiyat)} TL)" for q in sorted_rakipler[:3]
        ]
        kaynak_ozeti = ", ".join(parts) + f" ve {len(sorted_rakipler) - 3} kaynak daha"

    company_label = vehicle.company.name if vehicle.company_id else "Filonuz"
    gerekce = (
        f"{kaynak_ozeti} verilerine göre piyasa ortalaması {_format_tl(market_avg)} TL. "
        f"Bu ortalamanın %{undercut_pct:.0f} altında kalarak rekabet avantajı sağlamak "
        f"için önerilen fiyat {_format_tl(onerilen)} TL olarak belirlenmiştir. "
        f"Yield motoru (doluluk/km) referansı: {_format_tl(internal.final_price)} TL — "
        f"{internal.reason}{floor_note}"
    )

    ai_tavsiyesi = (
        f"{company_label} için günlük {_format_tl(onerilen)} TL, "
        f"{len(rakipler)} rakip kaynağın ortalamasının %{undercut_pct:.0f} altında "
        f"rekabetçi bir konum sunar."
    )

    return MarketPricingAdvice(
        vehicle_id=vehicle_id,
        onerilen_fiyat=onerilen,
        ai_tavsiyesi=ai_tavsiyesi,
        gerekce=gerekce,
        piyasa_ortalamasi=round(market_avg, 2),
        rakip_sayisi=len(rakipler),
        rakipler=rakipler,
        yield_fiyat=internal.final_price,
        yield_gerekce=internal.reason,
        taban_fiyat=internal.base_price,
    )


def upsert_competitor_prices(
    vehicle: Vehicle,
    entries: list[dict],
) -> list[CompetitorPrice]:
    """Kaynak adına göre rakip fiyatlarını oluşturur veya günceller."""
    sipp = _vehicle_sipp_code(vehicle)
    saved: list[CompetitorPrice] = []

    for entry in entries:
        source = str(entry.get("kaynak") or entry.get("source_name") or "").strip()
        if not source:
            continue
        raw_price = entry.get("gunluk_fiyat", entry.get("daily_price"))
        if raw_price is None or raw_price == "":
            continue
        price = Decimal(str(raw_price))
        if price <= 0:
            continue

        similar = str(
            entry.get("benzer_arac") or entry.get("similar_vehicle") or ""
        ).strip()

        row, _ = CompetitorPrice.objects.update_or_create(
            vehicle=vehicle,
            source_name=source,
            defaults={
                "daily_price": price,
                "sipp_code": sipp,
                "similar_vehicle": similar,
            },
        )
        saved.append(row)

    return saved
