"""Veritabanı ve kod tabanlı risk kuralı yükleme.

Domain katmanı (``backend.domain.risk``) saf iş kuralları içerir ve Django
ORM'e dokunmaz — bu yüzden DB'den kural seti okuyan bu orkestrasyon burada,
application katmanında yaşar (bkz. audit bulgusu #20).
"""

from __future__ import annotations

from backend.apps.risk_checks.models import (
    RuleDefinition,
    RuleEngineType,
    RuleSet,
)
from backend.domain.risk.rules import build_default_risk_rules
from backend.domain.rule_engine.engine import RuleDefinitionData, RuleEngine
from backend.domain.shared.enums import RuleEffect

_DEFAULT_RULES = build_default_risk_rules()
_PREDICATE_BY_CODE = {rule.code: rule.predicate for rule in _DEFAULT_RULES}


def _rule_from_db(defn: RuleDefinition) -> RuleDefinitionData | None:
    predicate = _PREDICATE_BY_CODE.get(defn.code)
    if predicate is None:
        return None
    try:
        effect = RuleEffect(defn.effect)
    except ValueError:
        effect = RuleEffect.ADD_SCORE
    return RuleDefinitionData(
        code=defn.code,
        priority=defn.priority,
        effect=effect,
        points=defn.points,
        message=defn.message,
        predicate=predicate,
    )


def load_risk_rules(company_id: int) -> list[RuleDefinitionData]:
    """Aktif DB kural setini yükler; yoksa kod tabanlı varsayılanlara düşer."""
    rule_set = (
        RuleSet.objects.filter(
            company_id=company_id,
            engine=RuleEngineType.RISK,
            is_active=True,
        )
        .order_by("-effective_from", "-created_at")
        .first()
    )
    if rule_set is None:
        return build_default_risk_rules()

    db_rules = list(rule_set.rules.filter(is_active=True).order_by("priority", "code"))
    if not db_rules:
        return build_default_risk_rules()

    loaded = [_rule_from_db(defn) for defn in db_rules]
    resolved = [rule for rule in loaded if rule is not None]
    return resolved if resolved else build_default_risk_rules()


def build_risk_engine(company_id: int) -> RuleEngine:
    return RuleEngine("RISK", load_risk_rules(company_id))
