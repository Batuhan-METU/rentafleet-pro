"""Nakit fırsat maliyeti — MALIYET_HESAPLAMA_METODOLOJISI §3.2.

Nakit/özkaynak ile finanse edilen tutarın alternatif maliyeti (o parayı
bankaya yatırsaydı kazanılacak faiz). Kredinin kendi taksit vadesiyle
kendiliğinden bitmesine paralel olarak, nakit fırsat maliyeti de şirket
ayarındaki varsayılan vade (``cash_opportunity_term_months``, filoya giriş
tarihinden itibaren) dolunca durur — bu, kullanıcıyla netleştirilmiş bir iş
kararıdır (araç filoda kalmaya devam etse bile). Karma finansmanlı
araçlarda sadece nakit kısmına uygulanır.

Mevduat faizi hesabı, Türkiye'deki standart mevduat faizi kuralını izler:
getiri = (Anapara × Faiz Oranı × Gün Sayısı) / 36500 artık olmayan yıllarda,
/36600 artık yıllarda (yılda 365 değil 366 gün olduğu için, aynı oran daha
fazla güne yayılır ve günlük pay biraz düşer). Bir dönem birden fazla takvim
yılına yayılıyorsa (ör. Aralık'tan Ocak'a), her yılın kendi payı o yılın
kendi bölenle (365/366) ayrı ayrı hesaplanıp toplanır — tek bir "sabit
günlük oran × toplam gün" çarpımı YETERLİ DEĞİLDİR, çünkü yıllar arası
bölen (365 vs 366) değişebilir.
"""

from __future__ import annotations

from calendar import isleap
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from backend.apps.vehicle_finance.choices import FinancingType
from backend.apps.vehicle_finance.models import VehicleFinancialProfile
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.company_settings import (
    get_cost_settings,
)
from backend.infrastructure.services.cost_calculation.day_math import add_months
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _days_in_year(year: int) -> int:
    return 366 if isleap(year) else 365


def _days_by_calendar_year(start: date, end: date) -> dict[int, int]:
    """``start`` hariç, ``end`` dahil aralığı takvim yılına göre böler.

    Her gün, ait olduğu takvim yılına sayılır (ör. 25 Aralık 2027 hariç →
    5 Ocak 2028 dahil aralığında: 2027'ye 6 gün (26-31 Aralık), 2028'e 5 gün
    (1-5 Ocak) düşer). Bu bölünme, yıl sınırını aşan dönemlerde her yılın
    kendi 365/366 böleniyle ayrı hesaplanabilmesi için gereklidir.
    """
    if end <= start:
        return {}
    result: dict[int, int] = {}
    cursor = start
    while cursor < end:
        year = (cursor + timedelta(days=1)).year
        year_end = date(year, 12, 31)
        segment_end = min(end, year_end)
        result[year] = result.get(year, 0) + (segment_end - cursor).days
        cursor = segment_end
    return result


def _deposit_interest(cash_amount: Decimal, annual_rate: Decimal, start: date, end: date) -> Decimal:
    """Türk mevduat faizi formülü — (Anapara × Oran × Gün)/36500|36600, yıl yıl."""
    total = Decimal("0")
    for year, days in _days_by_calendar_year(start, end).items():
        total += cash_amount * annual_rate * Decimal(days) / Decimal(_days_in_year(year))
    return total


def get_financial_profile(vehicle: Vehicle) -> VehicleFinancialProfile | None:
    """Aracın finansal profili — yoksa ``None`` (§1.5: finansman tipi tamamen bilinmiyor)."""
    try:
        return vehicle.financial_profile
    except VehicleFinancialProfile.DoesNotExist:
        return None



def _cash_financed_amount(vehicle: Vehicle, profile: VehicleFinancialProfile) -> Decimal | None:
    """Nakit ile finanse edilen tutar — §1.5: eksikse None, asla 0 değil."""
    if profile.financing_type == FinancingType.LOAN:
        return None
    if profile.cash_financed_amount is not None:
        return Decimal(profile.cash_financed_amount)
    if profile.financing_type == FinancingType.CASH:
        # CASH'te ayrıca girilmemişse tüm satın alım fiyatı nakit kabul edilir.
        purchase = vehicle.purchase_price or profile.purchase_price
        return Decimal(purchase) if purchase else None
    return None


def _cash_amount_and_rate(vehicle: Vehicle) -> tuple[Decimal, Decimal] | None:
    """Vade kontrolünden bağımsız girdiler: (nakit_tutar, yıllık_mevduat_oranı)."""
    profile = get_financial_profile(vehicle)
    if profile is None:
        return None
    cash_amount = _cash_financed_amount(vehicle, profile)
    if cash_amount is None:
        return None
    settings = get_cost_settings(vehicle.company)
    return cash_amount, Decimal(settings.annual_deposit_rate)


def cash_opportunity_term_end_date(vehicle: Vehicle) -> date | None:
    """Fırsat maliyetinin son işleyeceği tarih — filoya_giriş_tarihi + şirket vade ayarı.

    ``fleet_entry_date`` yoksa ``None`` döner (§1.5).
    """
    if vehicle.fleet_entry_date is None:
        return None
    settings = get_cost_settings(vehicle.company)
    return add_months(vehicle.fleet_entry_date, settings.cash_opportunity_term_months)


def daily_cash_opportunity_cost(vehicle: Vehicle, as_of: date | None = None) -> Decimal | None:
    """§3.2 — güncel (marjinal) günlük oran: nakit_tutar × oran / (365|366).

    Bölen, ``as_of``'un takvim yılı artık yıl mı değil mi ona göre 365 ya da
    366 olur (Türk mevduat faizi kuralı) — bu yüzden "sabit" bir günlük oran
    değildir, yıl döndüğünde küçük bir sıçrama yapabilir.

    ``financial_profile`` yoksa, finansman tipi Kredi ise ya da nakit
    tutarı belirlenemiyorsa ``None`` döner (Bilinmiyor ≠ Sıfır). Vade
    tarihi (``cash_opportunity_term_end_date``) ``as_of``'a göre geçmişte
    kalmışsa ``Decimal("0.00")`` döner — kredinin vade sonrası "sıradaki
    taksit yok" davranışıyla aynı mantık: bileşen hâlâ uygulanabilir,
    sadece vadesi dolmuş.
    """
    inputs = _cash_amount_and_rate(vehicle)
    if inputs is None:
        return None
    as_of = as_of or date.today()
    term_end = cash_opportunity_term_end_date(vehicle)
    if term_end is not None and as_of >= term_end:
        return Decimal("0.00")
    cash_amount, annual_rate = inputs
    return _round(cash_amount * annual_rate / Decimal(_days_in_year(as_of.year)))


def accrued_cash_opportunity_cost(vehicle: Vehicle, as_of: date) -> Decimal | None:
    """§3.2 — bugüne kadar tahakkuk eden mevduat faizi getirisi.

    Türk mevduat faizi kuralıyla (Anapara × Oran × Gün)/36500|36600 hesabı,
    dönem birden fazla takvim yılına yayılıyorsa HER YILIN KENDİ 365/366
    böleniyle ayrı ayrı hesaplanıp toplanır (bkz. ``_deposit_interest``) —
    tek bir sabit günlük oranla çarpmak, artık yıl geçişlerinde yanlış sonuç
    verir. Vade tarihinden sonraki günler sayılmaz — tahakkuk vade tarihinde
    donar ve bir daha artmaz.
    """
    inputs = _cash_amount_and_rate(vehicle)
    if inputs is None or vehicle.fleet_entry_date is None:
        return None
    term_end = cash_opportunity_term_end_date(vehicle)
    effective_as_of = min(as_of, term_end) if term_end is not None else as_of
    cash_amount, annual_rate = inputs
    return _round(_deposit_interest(cash_amount, annual_rate, vehicle.fleet_entry_date, effective_as_of))
