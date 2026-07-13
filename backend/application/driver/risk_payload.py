"""Sürücü risk API yanıtı oluşturma — tek kaynak."""

from __future__ import annotations

from typing import Any

from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.evaluation import RISK_LEVEL_LABELS


def build_driver_risk_payload(driver: Driver) -> dict[str, Any] | None:
    """Son risk değerlendirmesini API yanıtı formatında döner."""
    snapshot = driver.risk_snapshots.order_by("-computed_at").first()
    if snapshot is None and driver.current_risk_score is None:
        return None

    level = driver.risk_level or (snapshot.risk_level if snapshot else None)
    breakdown = snapshot.factor_breakdown if snapshot else {}
    if not isinstance(breakdown, dict):
        breakdown = {}

    audit = breakdown.get("audit") or {}
    vehicles = breakdown.get("eligible_vehicles")
    if vehicles is None and isinstance(audit, dict):
        vehicles = []

    blockers = audit.get("blockers", []) if isinstance(audit, dict) else []
    eligible = vehicles or []
    onaylandi = bool(level) and not blockers and bool(eligible)

    return {
        "skor": snapshot.risk_score if snapshot else driver.current_risk_score,
        "seviye": level,
        "seviye_label": RISK_LEVEL_LABELS.get(level or "", level or "—"),
        "onaylandi": onaylandi,
        "depozito": breakdown.get("deposit_amount"),
        "uygun_araclar": eligible,
        "uyarilar": audit.get("warnings", []) if isinstance(audit, dict) else [],
        "blokajlar": blockers,
        "faktorler": audit.get("outcomes", []) if isinstance(audit, dict) else [],
    }
