"""Sürücü risk alanlarını değerlendirme sonucundan kalıcı hale getirir."""

from __future__ import annotations

from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.evaluation import RiskEvaluationBundle


def persist_driver_risk_result(driver: Driver, bundle: RiskEvaluationBundle) -> None:
    """``current_risk_score``, ``risk_level`` ve ``risk_note`` alanlarını günceller."""
    level = bundle.risk_result.level or ""
    driver.current_risk_score = bundle.risk_result.score
    driver.risk_level = level
    if bundle.risk_result.warnings:
        driver.risk_note = "; ".join(bundle.risk_result.warnings[:3])
    elif bundle.risk_result.blockers:
        driver.risk_note = "; ".join(bundle.risk_result.blockers[:3])
    else:
        driver.risk_note = ""
    driver.save(update_fields=["current_risk_score", "risk_level", "risk_note", "updated_at"])
