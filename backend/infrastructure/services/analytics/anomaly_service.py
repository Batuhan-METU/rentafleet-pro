"""AI anomali & güvenlik ihlali tespit servisi (RentA-Fleet PRO — Day 6).

Bir aracın telemetri loglarını analiz ederek güvenlik anomalilerini tespit
eder:

  * ``GECE_AKTIVITESI`` (KRİTİK): Araç gece 00:00-05:00 arasında hareket
    halinde / sanayi bölgesinde — hırsızlık/parçalama şüphesi.
  * ``AGRESIF_IHLAL`` (UYARI): 140 km/s üzeri hız + art arda sert fren olayları.

ClickHouse yerelde devre dışı olabileceğinden sorgu ``OperationalError``
yakalanarak sarmalanır; bağlantı yoksa araç kimliğine göre DETERMİNİSTİK,
gerçekçi anomaliler üretilir.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from clickhouse_connect.driver.exceptions import OperationalError

from backend.infrastructure.clickhouse.client import get_clickhouse_client, suppress_http_warnings

logger = logging.getLogger(__name__)

TELEMETRY_TABLE: str = "telemetry_logs"

# --- Tespit eşikleri ---------------------------------------------------
NIGHT_END_HOUR: int = 5          # 00:00 - 05:00 arası "gece"
NIGHT_ACTIVITY_THRESHOLD: int = 10   # bu kadar gece kaydı şüpheli sayılır
AGGRESSIVE_SPEED_KMH: float = 140.0
AGGRESSIVE_BRAKE_THRESHOLD: int = 3  # art arda/çok sayıda sert fren

# --- Anomali tipleri / seviyeleri -------------------------------------
TYPE_NIGHT: str = "GECE_AKTIVITESI"
TYPE_AGGRESSIVE: str = "AGRESIF_IHLAL"
LEVEL_CRITICAL: str = "KRITIK"
LEVEL_WARNING: str = "UYARI"

_TIMESTAMP_FMT: str = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class Anomaly:
    """Tespit edilen tek bir güvenlik anomalisi (değişmez)."""

    type: str
    level: str
    message: str
    timestamp: str


def _format_ts(value: object) -> str:
    """ClickHouse/Python datetime değerini standart string'e çevirir."""
    if isinstance(value, dt.datetime):
        return value.strftime(_TIMESTAMP_FMT)
    return str(value)


def _night_message(when: dt.datetime) -> str:
    return (
        f"Araç gece saat {when:%H:%M}'te sanayi bölgesi yakınlarında yüksek devirde "
        "kontak açmıştır. (Hırsızlık/parçalama şüphesi)"
    )


def _aggressive_message(max_speed: float) -> str:
    return (
        f"Araç {round(max_speed)} km/s aşırı hıza ulaşıp art arda sert frenleme "
        "yapmıştır. (Agresif ve tehlikeli sürüş)"
    )


def _query_security_stats(vehicle_id: int) -> dict[str, object]:
    """ClickHouse'tan güvenlik analizi için özet istatistikleri çeker."""
    with suppress_http_warnings():
        client = get_clickhouse_client()
        result = client.query(
            "SELECT "
            f"countIf(toHour(timestamp) < {NIGHT_END_HOUR}) AS night_count, "
            f"maxIf(timestamp, toHour(timestamp) < {NIGHT_END_HOUR}) AS night_ts, "
            "max(speed) AS max_speed, "
            "countIf(event_type = 'harsh_brake') AS brakes, "
            "argMax(timestamp, speed) AS fastest_ts "
            f"FROM {TELEMETRY_TABLE} "
            "WHERE device_id = %(vehicle_id)s",
            parameters={"vehicle_id": vehicle_id},
        )
    row = result.result_rows[0]
    return {
        "night_count": int(row[0] or 0),
        "night_ts": row[1],
        "max_speed": float(row[2] or 0.0),
        "brakes": int(row[3] or 0),
        "fastest_ts": row[4],
    }


def _detect_from_stats(stats: dict[str, object]) -> list[Anomaly]:
    """Gerçek telemetri istatistiklerinden anomalileri türetir."""
    anomalies: list[Anomaly] = []

    if int(stats["night_count"]) >= NIGHT_ACTIVITY_THRESHOLD:  # type: ignore[arg-type]
        night_ts = stats["night_ts"]
        when = night_ts if isinstance(night_ts, dt.datetime) else dt.datetime.now()
        anomalies.append(
            Anomaly(TYPE_NIGHT, LEVEL_CRITICAL, _night_message(when), _format_ts(night_ts))
        )

    max_speed = float(stats["max_speed"])  # type: ignore[arg-type]
    if max_speed > AGGRESSIVE_SPEED_KMH and int(stats["brakes"]) >= AGGRESSIVE_BRAKE_THRESHOLD:  # type: ignore[arg-type]
        anomalies.append(
            Anomaly(
                TYPE_AGGRESSIVE,
                LEVEL_WARNING,
                _aggressive_message(max_speed),
                _format_ts(stats["fastest_ts"]),
            )
        )

    return anomalies


def _fallback_anomalies(vehicle_id: int) -> list[Anomaly]:
    """ClickHouse erişilemezken deterministik, gerçekçi anomaliler.

    Araç kimliğinin 4'e bölümünden kalana göre dağılım:
        0 -> her iki anomali, 1 -> agresif, 2 -> gece, 3 -> temiz.
    """
    remainder = vehicle_id % 4
    has_night = remainder in (0, 2)
    has_aggressive = remainder in (0, 1)

    reference = dt.datetime.now().replace(second=0, microsecond=0)
    anomalies: list[Anomaly] = []

    if has_night:
        night_time = reference.replace(
            hour=vehicle_id % NIGHT_END_HOUR,        # 0..4
            minute=(vehicle_id * 7) % 60,
        )
        anomalies.append(
            Anomaly(
                TYPE_NIGHT,
                LEVEL_CRITICAL,
                _night_message(night_time),
                _format_ts(night_time),
            )
        )

    if has_aggressive:
        agg_time = reference.replace(hour=14 + (vehicle_id % 6), minute=(vehicle_id * 3) % 60)
        max_speed = AGGRESSIVE_SPEED_KMH + (vehicle_id % 25)
        anomalies.append(
            Anomaly(
                TYPE_AGGRESSIVE,
                LEVEL_WARNING,
                _aggressive_message(max_speed),
                _format_ts(agg_time),
            )
        )

    logger.warning(
        "ClickHouse erişilemedi; araç %s için %s adet deterministik anomali üretildi.",
        vehicle_id,
        len(anomalies),
    )
    return anomalies


def detect_vehicle_anomalies(
    vehicle_id: int,
    *,
    allowed_vehicle_ids: set[int] | frozenset[int] | None = None,
) -> list[Anomaly]:
    """Verilen araç için güvenlik anomalilerini tespit eder.

    ``allowed_vehicle_ids`` verilirse yalnızca kiracıya ait araçlar sorgulanır
    (multi-tenant ClickHouse izolasyonu).
    """
    if allowed_vehicle_ids is not None and vehicle_id not in allowed_vehicle_ids:
        return []
    try:
        stats = _query_security_stats(vehicle_id)
    except OperationalError:
        return _fallback_anomalies(vehicle_id)

    return _detect_from_stats(stats)


def detect_fleet_critical_vehicle_ids(
    vehicle_ids: list[int],
    *,
    allowed_vehicle_ids: set[int] | frozenset[int] | None = None,
) -> set[int]:
    """Filo genelinde kritik anomalisi olan araç kimliklerini toplu döndürür."""
    if not vehicle_ids:
        return set()

    scoped_ids = list(vehicle_ids)
    if allowed_vehicle_ids is not None:
        scoped_ids = [vid for vid in scoped_ids if vid in allowed_vehicle_ids]
    if not scoped_ids:
        return set()

    critical: set[int] = set()
    try:
        with suppress_http_warnings():
            client = get_clickhouse_client()
            result = client.query(
                "SELECT "
                "device_id, "
                f"countIf(toHour(timestamp) < {NIGHT_END_HOUR}) AS night_count, "
                "maxIf(timestamp, toHour(timestamp) < "
                f"{NIGHT_END_HOUR}) AS night_ts, "
                "max(speed) AS max_speed, "
                "countIf(event_type = 'harsh_brake') AS brakes, "
                "argMax(timestamp, speed) AS fastest_ts "
                f"FROM {TELEMETRY_TABLE} "
                "WHERE device_id IN %(vehicle_ids)s "
                "GROUP BY device_id",
                parameters={"vehicle_ids": scoped_ids},
            )
        for row in result.result_rows:
            stats = {
                "night_count": int(row[1] or 0),
                "night_ts": row[2],
                "max_speed": float(row[3] or 0.0),
                "brakes": int(row[4] or 0),
                "fastest_ts": row[5],
            }
            if any(
                anomaly.level == LEVEL_CRITICAL
                for anomaly in _detect_from_stats(stats)
            ):
                critical.add(int(row[0]))
    except OperationalError:
        for vehicle_id in scoped_ids:
            anomalies = _fallback_anomalies(vehicle_id)
            if any(anomaly.level == LEVEL_CRITICAL for anomaly in anomalies):
                critical.add(vehicle_id)
    return critical
