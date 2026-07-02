"""Öngörücü bakım servisi (RentA-Fleet PRO — Day 12).

Her aracın kilometresine ve sürücü skoruna bakarak bir sonraki bakım hedefini
hesaplar ve risk durumunu belirler:

  * Standart bakım aralığı: 15.000 km.
    target_km = ((current_km // 15000) + 1) * 15000
  * Dinamik AI düzeltmesi: sürücü skoru < 70 (agresif sürüş) ise yıpranma payı
    olarak hedef 1.500 km öne çekilir.
  * kalan_km < 1000  -> SARI_UYARI
    kalan_km <= 0     -> ACIL_KIRMIZI (dinamik düzeltme bunu tetikleyebilir)

ClickHouse kapalıysa sürücü skoru deterministik fallback'e düşer; loglar
susturulur. Yalnızca ilgilenilmesi gereken araçlar (uyarılı) döndürülür.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from api.clickhouse_client import suppress_http_warnings
from api.models import Vehicle
from api.services.scoring_service import SAFE_DRIVER_THRESHOLD, score_for_vehicle_driver
from api.services.sipp_service import format_marka_model_sinif

MAINTENANCE_INTERVAL_KM = 15_000
WEAR_REDUCTION_KM = 1_500  # agresif sürüşte hor kullanım yıpranma payı
WARNING_THRESHOLD_KM = 1_000

STATUS_WARNING = "SARI_UYARI"
STATUS_CRITICAL = "ACIL_KIRMIZI"


@dataclass
class MaintenanceAlert:
    """Bir aracın bakım risk değerlendirmesi."""

    vehicle_id: int
    plate: str
    brand_model: str
    current_km: int
    target_km: int
    remaining_km: int
    progress_pct: float
    status: str
    aggressive: bool
    driver_score: int


@contextmanager
def _quiet_scoring_logs() -> Iterator[None]:
    """Filo geneli tarama sırasında skorlama servisinin araç-başı fallback
    uyarılarını susturur."""
    lg = logging.getLogger("api.services.scoring_service")
    previous = lg.level
    lg.setLevel(logging.ERROR)
    try:
        yield
    finally:
        lg.setLevel(previous)


def _evaluate(vehicle: dict, driver_score: int | None) -> MaintenanceAlert | None:
    """Tek araç için bakım durumunu hesaplar; uyarı yoksa None döner."""
    current_km = vehicle["current_km"] or 0
    base_target = ((current_km // MAINTENANCE_INTERVAL_KM) + 1) * MAINTENANCE_INTERVAL_KM

    aggressive = driver_score is not None and driver_score < SAFE_DRIVER_THRESHOLD
    target_km = base_target - (WEAR_REDUCTION_KM if aggressive else 0)

    remaining_km = target_km - current_km

    if remaining_km <= 0:
        status = STATUS_CRITICAL
    elif remaining_km < WARNING_THRESHOLD_KM:
        status = STATUS_WARNING
    else:
        return None  # bu araç henüz ilgilenilmeyi gerektirmiyor

    interval_start = base_target - MAINTENANCE_INTERVAL_KM
    window = max(1, target_km - interval_start)  # 0'a bölmeyi önle
    traveled = current_km - interval_start
    progress_pct = round(min(100.0, max(0.0, traveled / window * 100.0)), 1)

    return MaintenanceAlert(
        vehicle_id=vehicle["id"],
        plate=vehicle["plate_number"],
        brand_model=format_marka_model_sinif(
            vehicle["brand"], vehicle["model"], vehicle.get("sipp_code") or ""
        ),
        current_km=current_km,
        target_km=target_km,
        remaining_km=remaining_km,
        progress_pct=progress_pct,
        status=status,
        aggressive=aggressive,
        driver_score=driver_score if driver_score is not None else 0,
    )


def get_maintenance_alerts() -> list[MaintenanceAlert]:
    """İlgilenilmesi gereken araçların bakım uyarılarını üretir.

    En acil (en az kalan km) önce gelecek şekilde sıralanır.
    """
    vehicles = list(
        Vehicle.objects.values("id", "plate_number", "brand", "model", "sipp_code", "current_km")
    )
    if not vehicles:
        return []

    alerts: list[MaintenanceAlert] = []
    with suppress_http_warnings(), _quiet_scoring_logs():
        for vehicle in vehicles:
            score_result = score_for_vehicle_driver(vehicle["id"])
            driver_score = score_result.score if score_result else None
            alert = _evaluate(vehicle, driver_score)
            if alert is not None:
                alerts.append(alert)

    alerts.sort(key=lambda a: a.remaining_km)
    return alerts
