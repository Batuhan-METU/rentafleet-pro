"""Kiralama fiyat ekonomisi (RentA-Fleet PRO).

Mantık:
  * 1 yıllık planlama ufku (365 gün) — satış tarihi sorulmaz.
  * Yıllık yük = alış + kiraya hazırlık + (aylık işletme × 12)
  * Günlük maliyet = yıllık yük / 365
  * X günlük taban = günlük maliyet × X
  * Yakıt: dolu al–dolu bırak; ilk depo dolumu kiraya hazırlık masrafına dahil edilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from backend.apps.enuygun.models import CompetitorPrice
from backend.apps.floor_pricing.models import (
    RentalIncome,
    VehicleFinancialProfile,
)
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.common.date_helper import rental_window

PLANNING_HORIZON_DAYS: int = 365
DEFAULT_MONTHLY_MAINTENANCE: float = 2_500.0
ESTIMATED_INSURANCE_PCT_OF_PURCHASE: float = 0.045
ESTIMATED_MTV_PCT_OF_PURCHASE: float = 0.012

ESTIMATED_FIELD_DESCRIPTIONS: dict[str, str] = {
    "annual_kasko_cost / annual_traffic_insurance_cost": (
        "Kasko ve trafik sigortası girilmedi; alış fiyatının %4,5'i kullanıldı."
    ),
    "annual_mtv_cost": "MTV girilmedi; alış fiyatının %1,2'si kullanıldı.",
    "estimated_monthly_maintenance": "Aylık bakım girilmedi; 2.500 TL/ay varsayılan kullanıldı.",
}


@dataclass(frozen=True)
class CompetitorQuote:
    """Tek bir rakip kaynağın günlük fiyat satırı."""

    kaynak: str
    gunluk_fiyat: float


@dataclass(frozen=True)
class VehicleCostCard:
    purchase_price: float
    rental_prep_cost: float
    annual_insurance: float
    annual_kasko: float
    annual_traffic: float
    annual_mtv: float
    annual_inspection: float
    monthly_maintenance: float
    monthly_operating: float
    annual_operating: float
    annual_burden: float
    daily_cost: float
    estimated_fields: list[str]


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
        CompetitorQuote(kaynak=row.source_name, gunluk_fiyat=float(row.daily_price))
        for row in rows
    ]


def _purchase_price(vehicle: Vehicle) -> float:
    price = _f(vehicle.purchase_price)
    if price > 0:
        return price
    try:
        return _f(vehicle.financial_profile.purchase_price)
    except VehicleFinancialProfile.DoesNotExist:
        return 0.0


def build_vehicle_cost_card(vehicle: Vehicle) -> VehicleCostCard | None:
    """Araç maliyet kartı — yıllık yük ve günlük maliyet."""
    purchase = _purchase_price(vehicle)
    if purchase <= 0:
        return None

    estimated: list[str] = []

    kasko = _f(vehicle.annual_kasko_cost)
    traffic = _f(vehicle.annual_traffic_insurance_cost)
    if kasko > 0 or traffic > 0:
        annual_insurance = kasko + traffic
    else:
        annual_insurance = _f(vehicle.annual_insurance_cost)
        if annual_insurance <= 0:
            annual_insurance = purchase * ESTIMATED_INSURANCE_PCT_OF_PURCHASE
            estimated.append("annual_kasko_cost / annual_traffic_insurance_cost")

    mtv = _f(vehicle.annual_mtv_cost)
    if mtv <= 0:
        mtv = purchase * ESTIMATED_MTV_PCT_OF_PURCHASE
        estimated.append("annual_mtv_cost")

    inspection = _f(vehicle.annual_inspection_cost)
    maintenance = _f(vehicle.estimated_monthly_maintenance)
    if maintenance <= 0:
        maintenance = DEFAULT_MONTHLY_MAINTENANCE
        estimated.append("estimated_monthly_maintenance")

    monthly = (annual_insurance / 12.0) + (mtv / 12.0) + (inspection / 12.0) + maintenance
    annual_operating = monthly * 12.0

    prep = _f(vehicle.initial_industrial_expense)
    annual_burden = purchase + prep + annual_operating
    daily = annual_burden / PLANNING_HORIZON_DAYS

    return VehicleCostCard(
        purchase_price=purchase,
        rental_prep_cost=prep,
        annual_insurance=round(annual_insurance, 2),
        annual_kasko=round(kasko, 2),
        annual_traffic=round(traffic, 2),
        annual_mtv=round(mtv, 2),
        annual_inspection=round(inspection, 2),
        monthly_maintenance=round(maintenance, 2),
        monthly_operating=round(monthly, 2),
        annual_operating=round(annual_operating, 2),
        annual_burden=round(annual_burden, 2),
        daily_cost=round(daily, 2),
        estimated_fields=estimated,
    )


def build_vehicle_profit_summary(vehicle: Vehicle) -> dict:
    """Tamamlanan kiralamalardan biriken net kâr (gelir − dönem maliyeti)."""
    card = build_vehicle_cost_card(vehicle)
    if card is None:
        return {
            "biriken_kar": 0.0,
            "toplam_gelir": 0.0,
            "toplam_maliyet": 0.0,
            "kiralama_sayisi": 0,
            "kiralanan_gun": 0,
            "ortalama_kar_gun": 0.0,
        }

    incomes = list(RentalIncome.objects.filter(vehicle=vehicle).order_by("-start_date"))
    total_revenue = sum(_f(inc.total_income) for inc in incomes)
    rented_days = sum(inc.total_days for inc in incomes)
    total_cost = card.daily_cost * rented_days
    total_profit = total_revenue - total_cost

    return {
        "biriken_kar": round(total_profit, 2),
        "toplam_gelir": round(total_revenue, 2),
        "toplam_maliyet": round(total_cost, 2),
        "kiralama_sayisi": len(incomes),
        "kiralanan_gun": rented_days,
        "ortalama_kar_gun": round(total_profit / rented_days, 2) if rented_days > 0 else 0.0,
    }


def build_rental_quote(
    vehicle: Vehicle,
    rental_days: int,
    *,
    market_daily_average: float | None = None,
    offered_total_price: float | None = None,
) -> dict:
    """X günlük kiralama için taban fiyat, piyasa karşılaştırması ve kâr önizlemesi."""
    days = max(int(rental_days), 1)
    card = build_vehicle_cost_card(vehicle)

    if card is None:
        return {
            "maliyet_karti_var": False,
            "mesaj": "Satın alma fiyatı girilmeden kiralama fiyatı hesaplanamaz.",
        }

    period_floor = round(card.daily_cost * days, 2)
    daily_floor = card.daily_cost
    profit_summary = build_vehicle_profit_summary(vehicle)

    market_period = None
    market_warning = None
    if market_daily_average is not None and market_daily_average > 0:
        market_period = round(market_daily_average * days, 2)
        if market_period < period_floor:
            market_warning = (
                f"Dikkat: Piyasa toplamı ({market_period:,.0f} TL) bu dönemin maliyet "
                f"tabanının ({period_floor:,.0f} TL) altında. Bu fiyattan kiralamayın."
            ).replace(",", ".")

    profit = None
    profit_daily = None
    if offered_total_price is not None and offered_total_price > 0:
        profit = round(offered_total_price - period_floor, 2)
        profit_daily = round(profit / days, 2)

    return {
        "maliyet_karti_var": True,
        "kiralanan_gun": days,
        "planlama_ufku_gun": PLANNING_HORIZON_DAYS,
        "maliyet_karti": {
            "alis_fiyati": card.purchase_price,
            "kiraya_hazirlik": card.rental_prep_cost,
            "aylik_isletme": card.monthly_operating,
            "yillik_isletme": card.annual_operating,
            "yillik_toplam_yuk": card.annual_burden,
            "tahmini_alanlar": card.estimated_fields,
        },
        "gunluk_maliyet": daily_floor,
        "donem_taban_fiyat": period_floor,
        "gunluk_taban_fiyat": daily_floor,
        "piyasa_gunluk_ortalama": market_daily_average,
        "piyasa_donem_toplam": market_period,
        "piyasa_uyarisi": market_warning,
        "teklif_toplam": offered_total_price,
        "tahmini_kar": profit,
        "tahmini_kar_gunluk": profit_daily,
        "biriken_kar": profit_summary["biriken_kar"],
        "biriken_kar_ozeti": profit_summary,
        "mesaj": (
            f"{days} günlük kiralama için maliyet tabanınız {period_floor:,.0f} TL "
            f"(günlük {daily_floor:,.0f} TL).".replace(",", ".")
        ),
    }


def build_maliyet_analizi_payload(vehicle: Vehicle) -> dict | None:
    """Araç detay / oluşturma yanıtı için özet maliyet kartı (1 günlük referans)."""
    card = build_vehicle_cost_card(vehicle)
    if card is None:
        return None
    return {
        "gunluk_maliyet": card.daily_cost,
        "yillik_toplam_yuk": card.annual_burden,
        "aylik_isletme": card.monthly_operating,
        "planlama_ufku_gun": PLANNING_HORIZON_DAYS,
        "maliyet_karti": {
            "alis_fiyati": card.purchase_price,
            "kiraya_hazirlik": card.rental_prep_cost,
            "aylik_isletme": card.monthly_operating,
            "yillik_isletme": card.annual_operating,
            "yillik_toplam_yuk": card.annual_burden,
        },
        "tahmini_alanlar": card.estimated_fields,
        "mesaj": (
            f"1 yıllık planlama ufkuyla günlük maliyet {card.daily_cost:,.0f} TL "
            f"(yıllık yük {card.annual_burden:,.0f} TL).".replace(",", ".")
        ),
    }


def _is_field_estimated(card: VehicleCostCard, field_key: str) -> bool:
    return field_key in card.estimated_fields


def build_maliyet_dagilimi(card: VehicleCostCard) -> dict:
    """Maliyet kalemlerini ayrı satırlar halinde döner (matematik değişmez)."""
    return {
        "alis_fiyati": card.purchase_price,
        "kiraya_hazirlik": card.rental_prep_cost,
        "yillik_sigorta": card.annual_insurance,
        "yillik_kasko": card.annual_kasko,
        "yillik_trafik_sigortasi": card.annual_traffic,
        "yillik_mtv": card.annual_mtv,
        "yillik_muayene": card.annual_inspection,
        "aylik_bakim": card.monthly_maintenance,
        "yillik_bakim": round(card.monthly_maintenance * 12.0, 2),
        "aylik_isletme": card.monthly_operating,
        "yillik_isletme": card.annual_operating,
        "yillik_toplam_yuk": card.annual_burden,
        "gunluk_maliyet": card.daily_cost,
        "planlama_ufku_gun": PLANNING_HORIZON_DAYS,
    }


def build_tahmini_alanlar_payload(card: VehicleCostCard) -> list[dict]:
    """Tahmini alanlar ve kullanıcı dostu açıklamalar."""
    rows: list[dict] = []
    for field_key in card.estimated_fields:
        rows.append(
            {
                "alan": field_key,
                "aciklama": ESTIMATED_FIELD_DESCRIPTIONS.get(
                    field_key,
                    f"{field_key} için varsayılan değer kullanıldı.",
                ),
            }
        )
    return rows


def build_hesaplama_adimlari(card: VehicleCostCard, rental_days: int) -> list[dict]:
    """Waterfall adımları — mevcut formüllerin şeffaf dökümü."""
    days = max(int(rental_days), 1)
    period_floor = round(card.daily_cost * days, 2)
    insurance_est = _is_field_estimated(
        card, "annual_kasko_cost / annual_traffic_insurance_cost"
    )
    mtv_est = _is_field_estimated(card, "annual_mtv_cost")
    maint_est = _is_field_estimated(card, "estimated_monthly_maintenance")

    return [
        {
            "sira": 1,
            "baslik": "Araç Alış Fiyatı",
            "aciklama": "Aracın şirkete giriş maliyeti. 1 yıllık plana dahil edilir.",
            "formul": "Araç künyesi → purchase_price",
            "deger": card.purchase_price,
            "birim": "TL",
            "tahmini": False,
            "kaynak_alan": "purchase_price",
        },
        {
            "sira": 2,
            "baslik": "Kiraya Hazırlık Gideri",
            "aciklama": "Sanayi, aksesuar, detay ve ilk depo dolumu gibi tek seferlik masraflar.",
            "formul": "initial_industrial_expense",
            "deger": card.rental_prep_cost,
            "birim": "TL",
            "tahmini": False,
            "kaynak_alan": "initial_industrial_expense",
        },
        {
            "sira": 3,
            "baslik": "Yıllık Sigorta (Kasko + Trafik)",
            "aciklama": "Yıllık kasko ve zorunlu trafik sigortası toplamı.",
            "formul": (
                "kasko + trafik"
                if not insurance_est
                else f"alis_fiyati × {ESTIMATED_INSURANCE_PCT_OF_PURCHASE:.1%}"
            ),
            "deger": card.annual_insurance,
            "birim": "TL/yıl",
            "tahmini": insurance_est,
            "kaynak_alan": "annual_kasko_cost / annual_traffic_insurance_cost",
        },
        {
            "sira": 4,
            "baslik": "Yıllık MTV",
            "aciklama": "Motorlu Taşıtlar Vergisi.",
            "formul": (
                "annual_mtv_cost"
                if not mtv_est
                else f"alis_fiyati × {ESTIMATED_MTV_PCT_OF_PURCHASE:.1%}"
            ),
            "deger": card.annual_mtv,
            "birim": "TL/yıl",
            "tahmini": mtv_est,
            "kaynak_alan": "annual_mtv_cost",
        },
        {
            "sira": 5,
            "baslik": "Yıllık Muayene",
            "aciklama": "Periyodik araç muayenesi maliyeti.",
            "formul": "annual_inspection_cost (girilmezse 0)",
            "deger": card.annual_inspection,
            "birim": "TL/yıl",
            "tahmini": False,
            "kaynak_alan": "annual_inspection_cost",
        },
        {
            "sira": 6,
            "baslik": "Aylık Bakım Öngörüsü",
            "aciklama": "Periyodik bakım, lastik ve küçük onarımlar.",
            "formul": (
                "estimated_monthly_maintenance"
                if not maint_est
                else f"varsayılan {DEFAULT_MONTHLY_MAINTENANCE:,.0f} TL/ay".replace(",", ".")
            ),
            "deger": card.monthly_maintenance,
            "birim": "TL/ay",
            "tahmini": maint_est,
            "kaynak_alan": "estimated_monthly_maintenance",
        },
        {
            "sira": 7,
            "baslik": "Aylık İşletme Gideri",
            "aciklama": "Sigorta, MTV, muayene ve bakımın aylık toplamı.",
            "formul": "(sigorta/12) + (mtv/12) + (muayene/12) + bakim",
            "deger": card.monthly_operating,
            "birim": "TL/ay",
            "tahmini": insurance_est or mtv_est or maint_est,
            "kaynak_alan": None,
        },
        {
            "sira": 8,
            "baslik": "Yıllık İşletme Gideri",
            "aciklama": "12 aylık işletme gideri toplamı.",
            "formul": "aylik_isletme × 12",
            "deger": card.annual_operating,
            "birim": "TL/yıl",
            "tahmini": insurance_est or mtv_est or maint_est,
            "kaynak_alan": None,
        },
        {
            "sira": 9,
            "baslik": "Yıllık Toplam Yük",
            "aciklama": "Alış + hazırlık + yıllık işletme.",
            "formul": "alis + hazirlik + yillik_isletme",
            "deger": card.annual_burden,
            "birim": "TL/yıl",
            "tahmini": False,
            "kaynak_alan": None,
        },
        {
            "sira": 10,
            "baslik": "Günlük Maliyet (Başa Baş)",
            "aciklama": (
                f"Yıllık yük {PLANNING_HORIZON_DAYS} güne bölünür. "
                "Her gün en az bu kadar kazanılmalı."
            ),
            "formul": f"yillik_toplam_yuk / {PLANNING_HORIZON_DAYS}",
            "deger": card.daily_cost,
            "birim": "TL/gün",
            "tahmini": False,
            "kaynak_alan": None,
        },
        {
            "sira": 11,
            "baslik": "Kiralama Süresi",
            "aciklama": "Alış ve dönüş tarihleri arasındaki gün sayısı (en az 1).",
            "formul": "max(bitis - baslangic, 1)",
            "deger": days,
            "birim": "gün",
            "tahmini": False,
            "kaynak_alan": None,
        },
        {
            "sira": 12,
            "baslik": "Minimum Kurtaran Fiyat",
            "aciklama": "Bu tutarın altına fiyat verirseniz mevcut hesaba göre zarar yazarsınız.",
            "formul": "gunluk_maliyet × kiralanan_gun",
            "deger": period_floor,
            "birim": "TL",
            "tahmini": False,
            "kaynak_alan": None,
            "vurgulu": True,
        },
    ]


def build_piyasa_payload(
    rakipler: list[CompetitorQuote],
    rental_days: int,
    *,
    period_floor: float | None = None,
) -> dict:
    """Rakip fiyat özeti — taban fiyatı etkilemez."""
    days = max(int(rental_days), 1)
    prices = [q.gunluk_fiyat for q in rakipler]
    stats = None
    if prices:
        stats = {
            "min": round(min(prices), 2),
            "ortalama": round(sum(prices) / len(prices), 2),
            "max": round(max(prices), 2),
        }

    gunluk_ort = stats["ortalama"] if stats else None
    donem_toplam = round(gunluk_ort * days, 2) if gunluk_ort else None
    uyari = None
    if donem_toplam is not None and period_floor is not None and donem_toplam < period_floor:
        uyari = (
            f"Dikkat: Piyasa toplamı ({donem_toplam:,.0f} TL) bu dönemin maliyet "
            f"tabanının ({period_floor:,.0f} TL) altında. Bu fiyattan kiralamayın."
        ).replace(",", ".")

    return {
        "tabani_etkilemez": True,
        "teklif_sayisi": len(rakipler),
        "gunluk": stats,
        "donem_toplam": donem_toplam,
        "uyari": uyari,
        "teklifler": [
            {"kaynak": q.kaynak, "gunluk_fiyat": q.gunluk_fiyat}
            for q in rakipler
        ],
    }


def build_mudur_teklifi_payload(
    offered_total_price: float,
    period_floor: float,
    rental_days: int,
    *,
    gunluk_maliyet: float,
    biriken_kar: float = 0.0,
    piyasa: dict | None = None,
) -> dict:
    """Müdür teklifi kâr analizi — mevcut taban/piyasa matematiği değişmez."""
    days = max(int(rental_days), 1)
    teklif = float(offered_total_price)
    profit = round(teklif - period_floor, 2)
    profit_daily = round(profit / days, 2)
    offered_daily = round(teklif / days, 2)
    margin_pct = round((profit / teklif) * 100.0, 1) if teklif > 0 else None

    market_period = (piyasa or {}).get("donem_toplam")
    market_daily_stats = (piyasa or {}).get("gunluk") or {}
    market_avg_daily = market_daily_stats.get("ortalama")

    if profit < 0:
        durum = "zarar"
        durum_etiketi = "Tabanın Altında"
        durum_mesaji = (
            f"Teklifiniz maliyet tabanının {abs(profit):,.0f} TL altında. "
            "Bu fiyattan kiralama zarar yazar.".replace(",", ".")
        )
    elif profit == 0:
        durum = "taban"
        durum_etiketi = "Tam Taban"
        durum_mesaji = "Teklifiniz maliyet tabanına eşit; kâr veya zarar yok."
    else:
        durum = "kar"
        durum_etiketi = "Taban Üstü — Kârlı"
        durum_mesaji = (
            f"Teklifiniz tabanın {profit:,.0f} TL üzerinde. "
            f"Günlük kâr: {profit_daily:,.0f} TL.".replace(",", ".")
        )

    piyasa_karsilastirma = None
    piyasaya_gore_fark = None
    if market_period is not None:
        piyasaya_gore_fark = round(teklif - market_period, 2)
        if teklif < market_period:
            piyasa_karsilastirma = "piyasa_alti"
        elif teklif > market_period:
            piyasa_karsilastirma = "piyasa_ustu"
        else:
            piyasa_karsilastirma = "piyasa_esit"

    return {
        "teklif_toplam": teklif,
        "teklif_gunluk": offered_daily,
        "minimum_taban": period_floor,
        "taban_gunluk": gunluk_maliyet,
        "tahmini_kar": profit,
        "tahmini_kar_gunluk": profit_daily,
        "marj_yuzdesi": margin_pct,
        "taban_altinda": profit < 0,
        "tabana_gore_fark": profit,
        "piyasa_donem_toplam": market_period,
        "piyasa_gunluk_ortalama": market_avg_daily,
        "piyasaya_gore_fark": piyasaya_gore_fark,
        "piyasa_karsilastirma": piyasa_karsilastirma,
        "durum": durum,
        "durum_etiketi": durum_etiketi,
        "durum_mesaji": durum_mesaji,
        "biriken_kar_sonrasi": round(biriken_kar + profit, 2),
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
    """Fiyat karar destek ekranı — mevcut hesaplamaların şeffaf birleşimi."""
    days = max(int(rental_days), 1)
    card = build_vehicle_cost_card(vehicle)
    rakipler = competitor_quotes_for_vehicle(
        vehicle.pk,
        pickup_date=pickup_date,
        dropoff_date=dropoff_date,
    )
    if market_daily_average is None and rakipler:
        market_daily_average = sum(q.gunluk_fiyat for q in rakipler) / len(rakipler)

    quote = build_rental_quote(
        vehicle,
        days,
        market_daily_average=market_daily_average,
        offered_total_price=offered_total_price,
    )

    if not quote.get("maliyet_karti_var"):
        return {
            "maliyet_karti_var": False,
            "mesaj": quote.get("mesaj", "Maliyet hesaplanamadı."),
            "arac": {
                "id": vehicle.pk,
                "plaka": vehicle.plate_number,
                "marka_model": f"{vehicle.brand} {vehicle.model}",
            },
        }

    period_floor = quote["donem_taban_fiyat"]
    piyasa = build_piyasa_payload(rakipler, days, period_floor=period_floor)

    mudur_teklifi = None
    if offered_total_price is not None and offered_total_price > 0:
        mudur_teklifi = build_mudur_teklifi_payload(
            offered_total_price,
            period_floor,
            days,
            gunluk_maliyet=quote["gunluk_maliyet"],
            biriken_kar=quote.get("biriken_kar") or 0.0,
            piyasa=piyasa,
        )

    return {
        "maliyet_karti_var": True,
        "arac": {
            "id": vehicle.pk,
            "plaka": vehicle.plate_number,
            "marka_model": f"{vehicle.brand} {vehicle.model}",
            "km": vehicle.current_km,
        },
        "ozet": {
            "minimum_kurtaran_fiyat": period_floor,
            "gunluk_maliyet": quote["gunluk_maliyet"],
            "kiralanan_gun": days,
            "planlama_ufku_gun": PLANNING_HORIZON_DAYS,
            "mesaj": quote["mesaj"],
        },
        "maliyet_dagilimi": build_maliyet_dagilimi(card),
        "hesaplama_adimlari": build_hesaplama_adimlari(card, days),
        "tahmini_alanlar": build_tahmini_alanlar_payload(card),
        "piyasa": piyasa,
        "mudur_teklifi": mudur_teklifi,
        "gecmis_performans": quote.get("biriken_kar_ozeti"),
        "biriken_kar": quote.get("biriken_kar"),
        "kiralama": quote,
        "meta": {
            "hesaplama_surumu": "rental_economics_v1",
            "formul_ozeti": (
                "yillik_yuk = alis + hazirlik + isletme×12; "
                "gunluk = yuk/365; taban = gunluk × gun"
            ),
            "piyasa_tabani_etkilemez": True,
        },
        "kapsam_notlari": [
            {
                "baslik": "Gider kayıtları",
                "aciklama": (
                    "Araç gider defterindeki (VehicleExpense) tekil kayıtlar "
                    "maliyet tabanına henüz dahil edilmez."
                ),
            },
            {
                "baslik": "Amortisman",
                "aciklama": (
                    "Alış fiyatı amortisman eğrisine bölünmez; 365 günlük "
                    "planlama ufkuna doğrudan yayılır."
                ),
            },
            {
                "baslik": "Yakıt",
                "aciklama": (
                    "Dolu al–dolu bırak modeli kullanılır; işletme yakıt "
                    "maliyeti tabana eklenmez."
                ),
            },
        ],
    }