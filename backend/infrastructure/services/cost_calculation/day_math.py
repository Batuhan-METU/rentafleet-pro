"""Gün sayımı yardımcıları — MALIYET_HESAPLAMA_METODOLOJISI §1.4.

İki farklı, kasıtlı olarak bir arada kullanılan kural vardır:
  * ``period_days``          — dönem ağırlıklandırma (start-exclusive, end-inclusive)
  * ``bucket_days_in_range`` — kova/aralık gün sayımı (start-inclusive, end-inclusive)

KRİTİK TUZAK (§1.4): ``bucket_days_in_range``'de HER İKİ uç da (aracın
filoya giriş tarihi VE "bugün"/``as_of``) simetrik olarak kırpılmalıdır.
Sadece bugünün ayı için kırpma yapıp aracın filoya girdiği ilk (kısmi) ay
için kırpmayı unutmak, o ayın maliyetinin/gelirinin fazla hesaplanmasına
yol açar — bu, ziraatfilo_maliyet projesinde gerçekten yaşanmış bir
hatadır. Tek bir ``max()``/``min()`` çifti her iki ucu da kapsar; iki ayrı
özel durum kodu YAZILMAZ.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date


def period_days(
    period_start: date,
    period_end: date,
    entry_date: date | None = None,
) -> int:
    """Dönem ağırlıklandırma gün sayısı — start-exclusive, end-inclusive.

    Bir taksit/poliçe döneminin, önceki tarihten (dahil değil) bu tarihe
    (dahil) kadar kaç gün sürdüğünü verir (§3.1 Adım 2, §1.4a). Araç dönem
    içinde sonradan filoya girmişse (``entry_date`` dönem başlangıcından
    sonraysa), sayım ``entry_date``'ten başlar.

    Dönem tamamen ``entry_date``'ten önce kalıyorsa ya da ``period_end``
    efektif başlangıçtan sonra değilse 0 döner.
    """
    effective_start = max(period_start, entry_date) if entry_date else period_start
    if period_end <= effective_start:
        return 0
    return (period_end - effective_start).days


def bucket_days_in_range(
    range_start: date,
    range_end: date,
    *,
    entry_date: date,
    as_of: date,
) -> int:
    """Kova (bucket) gün sayımı — start-inclusive, end-inclusive (+1).

    "Bu ay/aralık içinde araç kaç gün fiilen filodaydı" sorusu için
    kullanılır (§1.4b) — hem ``range_start`` hem ``range_end`` dahildir.
    İki uç da simetrik olarak kırpılır: ``entry_date`` aralığın ortasına
    denk geliyorsa sayım oradan başlar, ``as_of`` aralığın ortasına denk
    geliyorsa sayım orada biter. Bu simetri, §1.4'te anlatılan (yalnızca
    tek ucun kırpılmasından kaynaklanan) gerçek hatayı önler.
    """
    effective_start = max(range_start, entry_date)
    effective_end = min(range_end, as_of)
    if effective_end < effective_start:
        return 0
    return (effective_end - effective_start).days + 1


def add_months(start: date, months: int) -> date:
    """``start``'a takvim-doğru ``months`` ay ekler (kredi taksit vadeleri için).

    Gün, hedef ayın son gününü aşarsa o aya kırpılır (ör. 31 Ocak + 1 ay
    → 28/29 Şubat), standart dateutil.relativedelta davranışıyla aynıdır.
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)
