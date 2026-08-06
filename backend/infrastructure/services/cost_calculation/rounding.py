"""Ortak TL yuvarlama hassasiyeti.

Tüm maliyet/fiyat hesaplama modülleri paraları kuruşa (2 ondalık) yuvarlar —
bu sabit önceden 7 ayrı dosyada (ve ``application/rental/return_processing``
içinde ``_CENTS`` adıyla bir kez daha) birebir aynı değerle tekrar
tanımlanmıştı.
"""

from __future__ import annotations

from decimal import Decimal

TWO_PLACES = Decimal("0.01")
