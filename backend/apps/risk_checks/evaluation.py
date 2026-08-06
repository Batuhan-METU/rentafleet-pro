"""Müşteri risk değerlendirmesi — risk_checks uygulama API'si."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.application.rental.driver_eligibility import recommend_vehicles
from backend.application.risk.rule_loader import build_risk_engine
from backend.apps.customer_profiles.models import Driver
from backend.domain.deposit.engine import effective_deposit_percent
from backend.domain.risk.engine import RiskEngine
from backend.domain.rule_engine.audit import engine_result_to_audit_dict
from backend.domain.shared.types import CustomerSnapshot, EngineResult

RISK_LEVEL_LABELS = {
    "VERY_LOW": "Çok Düşük",
    "LOW": "Düşük",
    "MEDIUM": "Orta",
    "HIGH": "Yüksek",
    "VERY_HIGH": "Çok Yüksek",
}


@dataclass(frozen=True)
class RiskEvaluationBundle:
    risk_result: EngineResult
    audit: dict[str, Any]
    vehicles: tuple[dict[str, Any], ...]
    deposit: str | None
    deposit_percent: str | None
    approved: bool
    risk_level_label: str
    factors: tuple[dict[str, Any], ...]


def evaluate_customer_risk(
    driver: Driver,
    snapshot: CustomerSnapshot,
    *,
    company_id: int,
) -> RiskEvaluationBundle:
    """Risk motoru + uygunluk + depozito hesabını tek noktada çalıştırır.

    Araç önerisi (``recommend_vehicles``) ve depozito oranı SADECE risk
    onaylanmış VE en az bir seviye/segment eşleşmesi varsa hesaplanır —
    aksi halde ikisi de boş/None kalır ve ``approved`` False olur. Depozito
    burada bilerek yalnızca ORAN olarak üretilir (TL tutarı değil): bu
    değerlendirme anında henüz kesin bir kiralama fiyatı bilinmeyebilir,
    tutar hesaplaması gerçek fiyat belli olduğunda frontend'de yapılır.
    """
    resolved_company_id = company_id or driver.company_id
    engine = RiskEngine(build_risk_engine(resolved_company_id))
    risk_result = engine.evaluate(snapshot)
    audit = engine_result_to_audit_dict(risk_result)

    # Depozito, aracın alım fiyatının değil KİRALAMA FİYATININ bir yüzdesidir
    # (bkz. domain/deposit/engine.py). Bu değerlendirme anında henüz bir
    # kiralama fiyatı anlaşılmamış olabileceği için burada yalnızca oranı
    # (VIP/müşteri skoru indirimleri ve ilk kiralama sürşarjı uygulanmış
    # nihai oran) üretilir; TL tutarı fiyatlandırma → sürücü akışında,
    # gerçek kiralama fiyatı bilindiğinde frontend tarafında hesaplanır.
    vehicles: list[dict[str, Any]] = []
    deposit = None
    deposit_percent = None
    if risk_result.approved and risk_result.level:
        vehicles = recommend_vehicles(driver.company_id, risk_result.level)
        deposit_percent_val = effective_deposit_percent(
            risk_result.level,
            vip_tier=snapshot.vip_tier,
            customer_score=driver.current_customer_score,
            is_first_rental=snapshot.is_first_rental,
        )
        deposit_percent = str(deposit_percent_val) if deposit_percent_val is not None else None

    level = risk_result.level or ""
    factors = tuple(
        {
            "code": outcome.code,
            "points": outcome.points,
            "message": outcome.message,
        }
        for outcome in risk_result.outcomes
        if outcome.effect.value == "ADD_SCORE"
    )

    return RiskEvaluationBundle(
        risk_result=risk_result,
        audit=audit,
        vehicles=tuple(vehicles),
        deposit=deposit,
        deposit_percent=deposit_percent,
        approved=risk_result.approved and bool(vehicles),
        risk_level_label=RISK_LEVEL_LABELS.get(level, level or "—"),
        factors=factors,
    )
