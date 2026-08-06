"""Depozito hesaplama motoru.

Depozito, aracın alım/liste fiyatının değil, KİRALAMA FİYATININ (fiyatlandırma
ekranında anlaşılan tutarın) risk seviyesine göre bir yüzdesidir — düşük
riskte kiralama fiyatının %10'u, yüksek riskte %30'u gibi. Sürücü risk
değerlendirmesi anında henüz bir kiralama fiyatı belli olmayabileceği için
bu modül asıl olarak *oranı* (`effective_deposit_percent`) üretir; TL
tutarı ancak gerçek kiralama fiyatı bilindiğinde `calculate_deposit` ile
hesaplanır (bkz. fiyatlandırma → sürücü akışı).
"""

from __future__ import annotations

from decimal import Decimal

from backend.domain.shared.enums import RiskLevel

DEPOSIT_PERCENT_BY_RISK: dict[RiskLevel, Decimal] = {
    RiskLevel.VERY_LOW: Decimal("0.10"),
    RiskLevel.LOW: Decimal("0.15"),
    RiskLevel.MEDIUM: Decimal("0.20"),
    RiskLevel.HIGH: Decimal("0.30"),
    RiskLevel.VERY_HIGH: Decimal("0"),
}

VIP_DEPOSIT_DISCOUNT = Decimal("0.30")
HIGH_CUSTOMER_SCORE_THRESHOLD = 80
CUSTOMER_SCORE_DEPOSIT_DISCOUNT = Decimal("0.20")
FIRST_RENTAL_SURCHARGE = Decimal("0.25")


def deposit_percent_for_risk(risk_level: str) -> Decimal | None:
    """Risk seviyesine karşılık gelen taban depozito oranını döner (VERY_HIGH/geçersiz için None)."""
    try:
        level = RiskLevel(risk_level)
    except ValueError:
        return None
    if level == RiskLevel.VERY_HIGH:
        return None
    return DEPOSIT_PERCENT_BY_RISK[level]


def effective_deposit_percent(
    risk_level: str,
    *,
    vip_tier: str = "NONE",
    customer_score: int | None = None,
    is_first_rental: bool = False,
) -> Decimal | None:
    """VIP/müşteri skoru indirimleri ve ilk kiralama sürşarjı uygulanmış nihai oran."""
    percent = deposit_percent_for_risk(risk_level)
    if percent is None:
        return None

    level = RiskLevel(risk_level)

    if vip_tier in {"SILVER", "GOLD", "PLATINUM"}:
        percent *= Decimal("1") - VIP_DEPOSIT_DISCOUNT

    if customer_score is not None and customer_score >= HIGH_CUSTOMER_SCORE_THRESHOLD:
        percent *= Decimal("1") - CUSTOMER_SCORE_DEPOSIT_DISCOUNT

    if is_first_rental and level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
        percent *= Decimal("1") + FIRST_RENTAL_SURCHARGE

    return percent.quantize(Decimal("0.0001"))


def calculate_deposit(
    risk_level: str,
    rental_price: Decimal,
    *,
    vip_tier: str = "NONE",
    customer_score: int | None = None,
    is_first_rental: bool = False,
) -> Decimal | None:
    """Anlaşılan kiralama fiyatı üzerinden nihai depozito tutarını hesaplar."""
    percent = effective_deposit_percent(
        risk_level,
        vip_tier=vip_tier,
        customer_score=customer_score,
        is_first_rental=is_first_rental,
    )
    if percent is None:
        return None

    return (Decimal(rental_price) * percent).quantize(Decimal("0.01"))
