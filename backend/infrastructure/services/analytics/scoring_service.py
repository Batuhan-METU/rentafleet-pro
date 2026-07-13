"""Sürücü skorlama servisi (RentA-Fleet PRO).

Skor **araca değil, sürücüye** aittir. ClickHouse telemetrisi, sürücünün
tüm kiralama dönemleri (``Rental``) boyunca filtrelenir ve olaylar toplanır:

    * Taban skor: 100
    * Her ``speed_violation`` (hız ihlali): -5 puan
    * Her ``harsh_brake`` (ani fren): -8 puan
    * Her ``harsh_acceleration`` (ani hızlanma): -6 puan
    * Alt sınır: 10

ClickHouse kapalıysa deterministik fallback (sürücü kimliğine göre) devreye girer.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from clickhouse_connect.driver.exceptions import OperationalError
from django.utils import timezone

from backend.infrastructure.clickhouse.client import get_clickhouse_client, suppress_http_warnings
from backend.apps.reservations.models import (
    Rental,
    RentalStatus,
)

logger = logging.getLogger(__name__)

BASE_SCORE: int = 100
MIN_SCORE: int = 10
SPEED_VIOLATION_PENALTY: int = 5
HARSH_BRAKE_PENALTY: int = 8
HARSH_ACCELERATION_PENALTY: int = 6
SAFE_DRIVER_THRESHOLD: int = 70

SPEED_VIOLATION_EVENT: str = "speed_violation"
HARSH_BRAKE_EVENT: str = "harsh_brake"
HARSH_ACCELERATION_EVENT: str = "harsh_acceleration"
TELEMETRY_TABLE: str = "telemetry_logs"


@dataclass(frozen=True)
class DriverScore:
    """Bir sürücünün skoru ve kırılımı."""

    driver_id: int
    score: int
    total_violations: int
    total_brakes: int
    total_accelerations: int
    rental_count: int
    is_fallback: bool


def _compute_score(
    total_violations: int,
    total_brakes: int,
    total_accelerations: int,
) -> int:
    raw_score = (
        BASE_SCORE
        - (SPEED_VIOLATION_PENALTY * total_violations)
        - (HARSH_BRAKE_PENALTY * total_brakes)
        - (HARSH_ACCELERATION_PENALTY * total_accelerations)
    )
    return max(MIN_SCORE, raw_score)


def driver_comment(score: int) -> str:
    return "Güvenli Sürücü" if score >= SAFE_DRIVER_THRESHOLD else "Agresif Sürücü"


def _naive_utc(dt: datetime) -> datetime:
    """ClickHouse DateTime ile karşılaştırma için timezone bilgisini atar."""
    if timezone.is_aware(dt):
        return timezone.make_naive(dt, timezone.utc)
    return dt


def _query_event_counts_for_period(
    vehicle_id: int,
    started_at: datetime,
    ended_at: datetime,
) -> dict[str, int]:
    """Belirli araç + zaman aralığındaki olay sayıları."""
    with suppress_http_warnings():
        client = get_clickhouse_client()
        result = client.query(
            f"SELECT event_type, count() AS cnt FROM {TELEMETRY_TABLE} "
            "WHERE device_id = %(vehicle_id)s "
            "AND timestamp >= %(started_at)s "
            "AND timestamp <= %(ended_at)s "
            "GROUP BY event_type",
            parameters={
                "vehicle_id": vehicle_id,
                "started_at": _naive_utc(started_at),
                "ended_at": _naive_utc(ended_at),
            },
        )
    return {str(row[0]): int(row[1]) for row in result.result_rows}


def _aggregate_driver_events(driver_id: int) -> tuple[dict[str, int], int]:
    """Sürücünün tüm kiralama dönemlerindeki olayları toplar."""
    rentals = list(
        Rental.objects.filter(driver_id=driver_id)
        .exclude(status=RentalStatus.CANCELLED)
        .values("vehicle_id", "started_at", "ended_at")
    )
    totals: dict[str, int] = defaultdict(int)
    now = timezone.now()

    for rental in rentals:
        end = rental["ended_at"] or now
        counts = _query_event_counts_for_period(
            rental["vehicle_id"],
            rental["started_at"],
            end,
        )
        for event, count in counts.items():
            totals[event] += count

    return dict(totals), len(rentals)


def _fallback_score(driver_id: int) -> DriverScore:
    total_violations = 1 + (driver_id % 4)
    total_brakes = driver_id % 3
    total_accelerations = driver_id % 2
    rental_count = max(1, driver_id % 5)
    score = _compute_score(total_violations, total_brakes, total_accelerations)
    logger.warning(
        "ClickHouse erişilemedi; sürücü %s için deterministik fallback skor üretildi (%s).",
        driver_id,
        score,
    )
    return DriverScore(
        driver_id=driver_id,
        score=score,
        total_violations=total_violations,
        total_brakes=total_brakes,
        total_accelerations=total_accelerations,
        rental_count=rental_count,
        is_fallback=True,
    )


def calculate_driver_score(driver_id: int) -> DriverScore:
    """Verilen sürücü için sürüş skorunu hesaplar."""
    try:
        counts, rental_count = _aggregate_driver_events(driver_id)
    except OperationalError:
        return _fallback_score(driver_id)

    if rental_count == 0:
        return DriverScore(
            driver_id=driver_id,
            score=BASE_SCORE,
            total_violations=0,
            total_brakes=0,
            total_accelerations=0,
            rental_count=0,
            is_fallback=False,
        )

    total_violations = counts.get(SPEED_VIOLATION_EVENT, 0)
    total_brakes = counts.get(HARSH_BRAKE_EVENT, 0)
    total_accelerations = counts.get(HARSH_ACCELERATION_EVENT, 0)
    score = _compute_score(total_violations, total_brakes, total_accelerations)

    return DriverScore(
        driver_id=driver_id,
        score=score,
        total_violations=total_violations,
        total_brakes=total_brakes,
        total_accelerations=total_accelerations,
        rental_count=rental_count,
        is_fallback=False,
    )


def score_for_vehicle_driver(vehicle_id: int) -> DriverScore | None:
    """Aracın aktif (veya son) kiracısının skorunu döndürür; kiracı yoksa None."""
    rental = (
        Rental.objects.filter(vehicle_id=vehicle_id, status=RentalStatus.ACTIVE)
        .order_by("-started_at")
        .first()
    )
    if rental is None:
        rental = (
            Rental.objects.filter(vehicle_id=vehicle_id)
            .exclude(status=RentalStatus.CANCELLED)
            .order_by("-started_at")
            .first()
        )
    if rental is None:
        return None
    return calculate_driver_score(rental.driver_id)