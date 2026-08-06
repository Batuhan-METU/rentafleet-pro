"""Live telemetry simulator (RentA-Fleet PRO — Day 9).

Runs an infinite loop that, every few seconds, advances every active
(``AVAILABLE`` / ``RENTED``) vehicle along a realistic path and emits a fresh
telemetry ping. Each tick:

  * advances GPS coordinates with a small random walk,
  * fluctuates speed (mean-reverting with occasional bursts / hard brakes),
  * drains fuel (refuels near empty),
  * nudges the vehicle's odometer (``current_km``) in SQLite,
  * upserts the durable ``VehicleLiveState`` snapshot (the cross-process,
    ClickHouse-independent "safe log mechanism" the live-stream API reads),
  * best-effort inserts the same row into ClickHouse for historical analytics.

Run with::

    python3 manage.py run_simulator
    python3 manage.py run_simulator --interval 3
    python3 manage.py run_simulator --once          # single tick (testing)
    python3 manage.py run_simulator --company-id 1  # yalnızca bir kiracı
    python3 manage.py run_simulator --all-tenants   # tüm kiracılar (ops)

The loop is robust: a failure in one tick is logged and the simulator keeps
running; Ctrl-C exits cleanly. It holds no growing in-memory state, so it
will not leak memory over long runs.
"""

from __future__ import annotations

import datetime as dt
import random
import time
from typing import Any

from clickhouse_connect.driver.exceptions import OperationalError
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from backend.apps.vehicles.models import (
    Vehicle,
    VehicleLiveState,
    VehicleStatus,
)
from backend.infrastructure.clickhouse.client import get_clickhouse_client, suppress_http_warnings

DEFAULT_INTERVAL_SECONDS = 5
TELEMETRY_TABLE = "telemetry_logs"
TELEMETRY_COLUMNS: tuple[str, ...] = (
    "device_id",
    "timestamp",
    "speed",
    "fuel_level",
    "latitude",
    "longitude",
    "event_type",
)

SPEED_VIOLATION_KMH = 120.0
HARSH_BRAKE_DROP_KMH = 30.0
MAX_SPEED_KMH = 160.0
ACTIVE_STATUSES = (VehicleStatus.AVAILABLE, VehicleStatus.RENTED)


class Command(BaseCommand):
    help = "Run the live telemetry simulator: emit a fresh ping per active vehicle every N seconds."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--interval",
            type=float,
            default=DEFAULT_INTERVAL_SECONDS,
            help=f"Seconds between ticks (default {DEFAULT_INTERVAL_SECONDS}).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single tick and exit (useful for testing).",
        )
        parser.add_argument(
            "--company-id",
            type=int,
            default=None,
            help="Yalnızca belirtilen kiracı (şirket) araçlarını simüle et.",
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            help="Tüm kiracıların araçlarını simüle et (platform operasyonu).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        interval: float = max(0.5, float(options["interval"]))
        run_once: bool = bool(options["once"])
        company_id: int | None = options.get("company_id")
        all_tenants: bool = bool(options.get("all_tenants"))

        if company_id is None and not all_tenants:
            self.stderr.write(
                self.style.ERROR(
                    "[SİMÜLATÖR] --company-id veya --all-tenants zorunludur (multi-tenant izolasyon)."
                )
            )
            return

        self._company_id = company_id
        self._all_tenants = all_tenants

        scope_msg = (
            f"kiracı #{company_id}"
            if company_id is not None
            else "tüm kiracılar"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"[SİMÜLATÖR] Canlı telemetri simülasyonu başladı ({scope_msg}, her {interval:g} sn). "
                "Durdurmak için Ctrl-C."
            )
        )

        try:
            while True:
                try:
                    count = self._tick()
                    self.stdout.write(
                        f"[SİMÜLATÖR] {count} araç için yeni anlık veriler üretildi."
                    )
                    self.stdout.flush()  # gerçek zamanlı log (çıktı dosyaya yönlendirilse de)
                except Exception as exc:  # noqa: BLE001 - keep the loop alive
                    # A single bad tick must not kill the long-running process.
                    self.stderr.write(
                        self.style.ERROR(f"[SİMÜLATÖR] Tick hatası (atlanıyor): {exc}")
                    )

                if run_once:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n[SİMÜLATÖR] Durduruldu. Güle güle!")
            )

    # ------------------------------------------------------------------
    # One simulation step
    # ------------------------------------------------------------------
    def _tick(self) -> int:
        """Advance all active vehicles by one step. Returns the count updated."""
        vehicle_qs = Vehicle.objects.filter(status__in=ACTIVE_STATUSES)
        if self._company_id is not None:
            vehicle_qs = vehicle_qs.filter(company_id=self._company_id)
        vehicles = list(vehicle_qs.select_related("live_state"))
        if not vehicles:
            return 0

        # Naive UTC for the ClickHouse DateTime column; tz-aware for the ORM's
        # ``updated_at`` (bulk_update does NOT auto-set auto_now fields, so we
        # set it explicitly to keep "son güncelleme" fresh).
        now_utc = dt.datetime.now(dt.UTC).replace(tzinfo=None)
        tz_now = timezone.now()

        vehicles_to_update: list[Vehicle] = []
        states_to_update: list[VehicleLiveState] = []
        states_to_create: list[VehicleLiveState] = []
        clickhouse_rows: list[tuple[Any, ...]] = []

        for vehicle in vehicles:
            state = getattr(vehicle, "live_state", None)
            is_new = state is None
            if is_new:
                state = self._seed_state(vehicle)
            # `getattr(..., None)` untyped döner (`Any | None`) — iki dalın
            # ikisi de burada state'i gerçek bir VehicleLiveState yapar.
            assert state is not None

            self._advance(state)
            state.updated_at = tz_now

            # Nudge the odometer by the distance covered this step (>=1 km when
            # actually moving, so the change is visible in the demo UI).
            km_delta = state.speed * DEFAULT_INTERVAL_SECONDS / 3600.0
            if state.speed > 10.0:
                km_delta = max(km_delta, 1.0)
            vehicle.current_km = (vehicle.current_km or 0) + int(round(km_delta))
            vehicles_to_update.append(vehicle)

            (states_to_create if is_new else states_to_update).append(state)

            clickhouse_rows.append(
                (
                    vehicle.pk,
                    now_utc,
                    round(state.speed, 2),
                    round(state.fuel_level, 2),
                    round(state.latitude, 6),
                    round(state.longitude, 6),
                    state.event_type,
                )
            )

        # Persist relational changes atomically (odometer + live snapshots).
        with transaction.atomic():
            if vehicles_to_update:
                Vehicle.objects.bulk_update(vehicles_to_update, ["current_km"])
            if states_to_create:
                VehicleLiveState.objects.bulk_create(states_to_create)
            if states_to_update:
                VehicleLiveState.objects.bulk_update(
                    states_to_update,
                    ["latitude", "longitude", "speed", "fuel_level", "event_type", "updated_at"],
                )

        # Best-effort historical insert into ClickHouse; never fatal locally.
        self._push_to_clickhouse(clickhouse_rows)

        return len(vehicles)

    # ------------------------------------------------------------------
    # Telemetry physics
    # ------------------------------------------------------------------
    @staticmethod
    def _seed_state(vehicle: Vehicle) -> VehicleLiveState:
        """Create an initial live state near Ankara for a vehicle's first ping."""
        return VehicleLiveState(
            vehicle=vehicle,
            latitude=VehicleLiveState.DEFAULT_LATITUDE + random.uniform(-0.05, 0.05),
            longitude=VehicleLiveState.DEFAULT_LONGITUDE + random.uniform(-0.05, 0.05),
            speed=random.uniform(40.0, 70.0),
            fuel_level=random.uniform(60.0, 100.0),
            event_type="normal",
        )

    @staticmethod
    def _advance(state: VehicleLiveState) -> None:
        """Mutate ``state`` in place to its next realistic telemetry sample."""
        previous_speed = state.speed

        # GPS random walk (~tens of meters per step).
        state.latitude += random.uniform(-0.0009, 0.0009)
        state.longitude += random.uniform(-0.0009, 0.0009)

        # Speed: mostly mean-reverting toward a comfortable cruise (~65 km/h),
        # with rare hard brakes and rare highway bursts (which breach limits).
        roll = random.random()
        if roll < 0.04:  # sudden hard deceleration -> harsh_brake
            speed = max(0.0, previous_speed - random.uniform(35.0, 60.0))
        elif roll < 0.09:  # highway burst, may exceed the limit
            speed = min(MAX_SPEED_KMH, previous_speed + random.uniform(30.0, 55.0))
        else:  # normal cruising, revert toward 65
            reversion = (65.0 - previous_speed) * 0.2
            speed = max(0.0, min(MAX_SPEED_KMH, previous_speed + reversion + random.uniform(-10.0, 10.0)))

        # Fuel drains with speed; refuel when near empty.
        state.fuel_level -= speed * 0.0015 + random.uniform(0.0, 0.05)
        if state.fuel_level <= 5.0:
            state.fuel_level = random.uniform(90.0, 100.0)
        state.fuel_level = max(0.0, state.fuel_level)

        state.event_type = Command._classify_event(speed, previous_speed)
        state.speed = speed

    @staticmethod
    def _classify_event(speed: float, previous_speed: float) -> str:
        """Derive an event_type from the speed profile."""
        if speed > SPEED_VIOLATION_KMH:
            return "speed_violation"
        if previous_speed - speed > HARSH_BRAKE_DROP_KMH:
            return "harsh_brake"
        if random.random() < 0.01:
            return "geofence_out"
        return "normal"

    # ------------------------------------------------------------------
    # Analytics sink
    # ------------------------------------------------------------------
    def _push_to_clickhouse(self, rows: list[tuple[Any, ...]]) -> None:
        """Insert this tick's rows into ClickHouse; skip silently if offline."""
        if not rows:
            return
        try:
            with suppress_http_warnings():
                client = get_clickhouse_client()
                client.insert(TELEMETRY_TABLE, rows, column_names=list(TELEMETRY_COLUMNS))
        except OperationalError:
            # ClickHouse down: the durable SQLite snapshot already has the
            # latest state, so live tracking keeps working. Nothing to do.
            pass