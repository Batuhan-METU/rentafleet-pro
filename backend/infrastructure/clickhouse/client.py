"""ClickHouse connectivity layer for RentA-Fleet PRO.

Wraps ``clickhouse-connect`` behind a small, typed helper so the rest of
the codebase never touches connection details directly. Configuration is
read from Django settings (which in turn are populated from environment
variables — see ``backend/settings.py`` and ``.env.example``).

Usage::

    from backend.infrastructure.clickhouse.client import get_clickhouse_client

    client = get_clickhouse_client()
    rows = client.query(
        "SELECT event_type, count() FROM telemetry_logs "
        "WHERE device_id = %(device_id)s AND timestamp >= %(since)s "
        "GROUP BY event_type",
        parameters={"device_id": 42, "since": "2026-01-01 00:00:00"},
    ).result_rows
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from django.conf import settings

# clickhouse-connect's Client is thread-safe for query execution, so a single
# process-wide client is reused. The lock only guards lazy initialization.
_client_lock = threading.Lock()


# Loggers that emit expected, redundant WARNINGs when ClickHouse is offline.
_NOISY_LOGGERS: tuple[str, ...] = (
    "clickhouse_connect.driver.httpclient",  # "Unexpected Http Driver Exception"
    "urllib3.connectionpool",                # connection retry warnings
)


@contextmanager
def suppress_http_warnings() -> Iterator[None]:
    """Temporarily silence the HTTP transport WARNINGs of a failed connection.

    On a refused/failed connection clickhouse-connect (and the underlying
    urllib3) log warnings before the error propagates. Callers that already
    report the failure with a friendlier message (services, seeding) can wrap
    the risky call — INCLUDING client creation, which is where the connection
    is actually established — in this context to keep logs clean. Original
    levels are always restored.
    """
    loggers = [logging.getLogger(name) for name in _NOISY_LOGGERS]
    previous_levels = [lg.level for lg in loggers]
    for lg in loggers:
        lg.setLevel(logging.ERROR)
    try:
        yield
    finally:
        for lg, level in zip(loggers, previous_levels):
            lg.setLevel(level)


@lru_cache(maxsize=1)
def _build_client() -> Client:
    """Create and memoize a single ClickHouse client for this process."""
    config: dict[str, Any] = settings.CLICKHOUSE

    return clickhouse_connect.get_client(
        host=config["HOST"],
        port=int(config["PORT"]),
        username=config["USER"],
        password=config["PASSWORD"],
        database=config["DATABASE"],
        secure=bool(config.get("SECURE", False)),
        connect_timeout=int(config.get("CONNECT_TIMEOUT", 10)),
        query_limit=0,  # 0 => no implicit row cap; callers control limits explicitly
        compress=True,
    )


def get_clickhouse_client() -> Client:
    """Return the shared, lazily-initialized ClickHouse client.

    Thread-safe: the first caller builds the client under a lock; subsequent
    callers get the memoized instance.
    """
    with _client_lock:
        return _build_client()


def reset_clickhouse_client() -> None:
    """Drop the cached client (e.g. after a connection error or in tests)."""
    with _client_lock:
        try:
            _build_client().close()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
        _build_client.cache_clear()


def ping() -> bool:
    """Lightweight health check used by readiness probes."""
    try:
        return get_clickhouse_client().query("SELECT 1").result_rows[0][0] == 1
    except Exception:  # noqa: BLE001
        return False


def ensure_database() -> None:
    """Create the configured analytics database if it does not yet exist.

    Connects WITHOUT binding to a database (which may not exist yet), issues
    ``CREATE DATABASE IF NOT EXISTS`` and disposes of the bootstrap client.
    Safe to call repeatedly; intended for seeding/bootstrap flows.
    """
    config: dict[str, Any] = settings.CLICKHOUSE
    bootstrap = clickhouse_connect.get_client(
        host=config["HOST"],
        port=int(config["PORT"]),
        username=config["USER"],
        password=config["PASSWORD"],
        secure=bool(config.get("SECURE", False)),
        connect_timeout=int(config.get("CONNECT_TIMEOUT", 10)),
    )
    try:
        bootstrap.command(f"CREATE DATABASE IF NOT EXISTS {config['DATABASE']}")
    finally:
        bootstrap.close()


def _strip_sql_comments(raw_sql: str) -> str:
    """Remove ``--`` line comments so statement splitting stays correct."""
    cleaned_lines: list[str] = []
    for line in raw_sql.splitlines():
        comment_idx = line.find("--")
        cleaned_lines.append(line if comment_idx == -1 else line[:comment_idx])
    return "\n".join(cleaned_lines)


def apply_schema(sql_path: Path | None = None) -> None:
    """Execute the telemetry DDL file (idempotent ``CREATE TABLE IF NOT EXISTS``).

    Intended for bootstrap scripts / management commands rather than request
    handling. Comments are stripped, then statements are split on ``;`` and
    run sequentially against the configured database.
    """
    path = sql_path or (
        Path(__file__).resolve().parent.parent / "sql" / "clickhouse_telemetry_logs.sql"
    )
    raw_sql = _strip_sql_comments(path.read_text(encoding="utf-8"))

    client = get_clickhouse_client()
    for statement in (s.strip() for s in raw_sql.split(";")):
        if statement:
            client.command(statement)
