"""Relational (PostgreSQL / OLTP) domain models for RentA-Fleet PRO.

This package holds the authoritative, transactional source of truth:
tenants (``Company``), their users (``CustomUser``) and the physical
fleet (``Vehicle``). High-volume, append-only telemetry does **not** live
here — it is streamed into ClickHouse (see
``backend/infrastructure/clickhouse/client.py`` and
``backend/infrastructure/sql/clickhouse_telemetry_logs.sql``).
"""

from .company import *  # noqa: F403
from .user import *  # noqa: F403
from .vehicle import *  # noqa: F403
from .driver import *  # noqa: F403
from .rental import *  # noqa: F403
from .finance import *  # noqa: F403
from .decision import *  # noqa: F403
