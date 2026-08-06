"""Risk skoru motoru."""

from __future__ import annotations

from backend.domain.rule_engine.engine import RuleEngine
from backend.domain.rule_engine.thresholds import (
    RISK_BLOCK_THRESHOLD,
    RISK_SCORE_MAX,
    RISK_SCORE_MIN,
    score_to_risk_level,
)
from backend.domain.shared.enums import RiskLevel
from backend.domain.shared.types import CustomerSnapshot, EngineResult


class RiskEngine:
    """Saf risk skoru motoru — hangi kural setinin kullanılacağı çağıranın
    sorumluluğudur (bkz. ``backend.application.risk.rule_loader.build_risk_engine``
    için DB'den kural yükleyen orkestrasyon). Domain katmanı ORM'e dokunmaz.
    """

    def __init__(self, rule_engine: RuleEngine) -> None:
        self._engine = rule_engine

    def evaluate(self, customer: CustomerSnapshot) -> EngineResult:
        """Kural motorunu çalıştırıp puanı [0, 100] aralığına sıkıştırır ve seviyeye çevirir.

        ``level == VERY_HIGH`` ile ``clamped >= RISK_BLOCK_THRESHOLD`` şu an
        aynı bandı (81-100) test ediyor gibi görünse de KASITLI olarak ayrı
        tutulur: seviye bantları (``RISK_LEVEL_BANDS``) ile blok eşiği
        (``RISK_BLOCK_THRESHOLD``) ayrı ayrı ayarlanabilir sabitlerdir —
        biri diğerinden bağımsız değiştirilirse (ör. blok eşiği 85'e
        çekilirse) bu ikili kontrol hâlâ doğru davranır.
        """
        base = self._engine.evaluate(customer)
        raw_score = base.score or 0
        clamped = max(RISK_SCORE_MIN, min(RISK_SCORE_MAX, raw_score))
        level = score_to_risk_level(clamped)

        blockers = list(base.blockers)
        if level == RiskLevel.VERY_HIGH and clamped >= RISK_BLOCK_THRESHOLD:
            blockers.append("Risk skoru çok yüksek — araç kiralanamaz.")

        return EngineResult(
            engine=base.engine,
            score=clamped,
            level=level.value,
            outcomes=base.outcomes,
            blockers=tuple(blockers),
            warnings=base.warnings,
            metadata={"block_threshold": RISK_BLOCK_THRESHOLD},
        )