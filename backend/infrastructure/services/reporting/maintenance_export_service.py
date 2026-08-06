"""Bakım Merkezi listesinin toplu Excel (.xlsx) raporunu üreten servis.

Bakım Merkezi ekranındaki üç kümeyi (Sağlıklı / Bakım Bekleyen / Acil)
tek sayfada raporlar — hepsi ``maintenance_service.get_maintenance_
statuses``'un döndürdüğü tek, homojen listeden gelir (artık ayrı bir
"sağlıklı araçlar" sorgusuna gerek yok).
"""

from __future__ import annotations

from collections.abc import Iterable

from backend.infrastructure.services.analytics.maintenance_service import (
    STATUS_CRITICAL,
    STATUS_HEALTHY,
    MaintenanceAlert,
)
from backend.infrastructure.services.reporting.excel import (
    KM_FORMAT,
    PERCENT_FORMAT,
    build_worksheet_bytes,
)

_HEADERS: tuple[str, ...] = (
    "Plaka",
    "Marka / Model",
    "Bakım Durumu",
    "Güncel KM",
    "Son Bakım Tarihi",
    "Son Bakım KM",
    "Hedef KM",
    "Kalan KM",
    "İlerleme (%)",
    "Hedef Tarih",
    "Kalan Gün",
)

_NUMBER_FORMATS: dict[int, str] = {
    4: KM_FORMAT,
    6: KM_FORMAT,
    7: KM_FORMAT,
    8: KM_FORMAT,
    9: PERCENT_FORMAT,
}

_STATUS_TR = {
    STATUS_CRITICAL: "Acil",
    STATUS_HEALTHY: "Sağlıklı",
}


def _status_row(alert: MaintenanceAlert) -> tuple[object, ...]:
    return (
        alert.plate,
        alert.brand_model,
        _STATUS_TR.get(alert.status, "Yaklaşıyor"),
        alert.current_km,
        alert.last_maintenance_date,
        alert.last_maintenance_km,
        alert.target_km,
        alert.remaining_km,
        alert.progress_pct,
        alert.target_date,
        alert.remaining_days,
    )


def build_maintenance_workbook(statuses: Iterable[MaintenanceAlert]) -> bytes:
    """Bakım durumları için .xlsx içeriği üretir (km + tarih boyutu birlikte)."""
    rows = [_status_row(alert) for alert in statuses]
    return build_worksheet_bytes(
        "Bakım Merkezi",
        _HEADERS,
        rows,
        number_formats=_NUMBER_FORMATS,
    )
