"""Seed the local stores with realistic demo data.

Run with::

    python3 manage.py seed_data
    python3 manage.py seed_data --flush                 # wipe first
    python3 manage.py seed_data --companies 10 --vehicles 100 --logs-per-vehicle 1000

What it does:
  1. Relational (SQLite via Django ORM): inserts fake ``Company`` and
     ``Vehicle`` rows.
  2. Analytics (ClickHouse via clickhouse-connect): generates a coherent
     historical telemetry trajectory per vehicle and bulk-inserts it into
     ``telemetry_logs`` in batches, using the native column-oriented insert
     path to stay fast and avoid HTTP timeouts.

The telemetry is *correlated*, not pure noise: each vehicle performs a GPS
random-walk around Ankara, fuel drains as it drives (with occasional
refuels), and speed fluctuates — deliberately producing ``speed_violation``
and ``harsh_brake`` events for the future anomaly-detection model.
"""

from __future__ import annotations

import datetime as dt
import random
from typing import Any, Iterable, Iterator

from clickhouse_connect.driver.exceptions import OperationalError
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone
from faker import Faker

from backend.infrastructure.clickhouse.client import (
    apply_schema,
    ensure_database,
    get_clickhouse_client,
    suppress_http_warnings,
)
from backend.models import Company, CustomUser, Driver, Gender, Rental, RentalStatus, UserRole, Vehicle, VehicleStatus

# --- Tunable defaults --------------------------------------------------
DEFAULT_COMPANIES = 1  # single-tenant: kurulum başına tek şirket
DEFAULT_VEHICLES = 100
DEFAULT_DRIVERS = 80
DEFAULT_LOGS_PER_VEHICLE = 1_000  # 100 vehicles * 1_000 => 100_000 telemetry rows
CLICKHOUSE_INSERT_BATCH = 10_000  # rows per ClickHouse insert call
TELEMETRY_TABLE = "telemetry_logs"

# Column order MUST match the tuples produced in `_build_vehicle_trajectory`.
TELEMETRY_COLUMNS: tuple[str, ...] = (
    "device_id",
    "timestamp",
    "speed",
    "fuel_level",
    "latitude",
    "longitude",
    "event_type",
)

# --- Domain constants --------------------------------------------------
ANKARA_CENTER = (39.9334, 32.8597)  # (latitude, longitude)

# (marka, model, SIPP) — Enuygun eşleştirmesini test etmek için çeşitli kodlar.
# resolve_sipp() çoğu modelde ECMR (manuel) döndürür; seed'de kodu açıkça yazıyoruz.
SEED_VEHICLE_CATALOG: tuple[tuple[str, str, str], ...] = (
    # Ekonomik hatch — EC**
    ("Renault", "Clio", "ECAR"),
    ("Renault", "Clio", "ECMR"),
    ("Renault", "Clio", "ECAD"),
    ("Hyundai", "i20", "ECAR"),
    ("Hyundai", "i20", "ECMR"),
    ("Opel", "Corsa", "ECAR"),
    ("Opel", "Corsa", "ECAD"),
    ("Citroen", "C3", "ECAR"),
    ("Kia", "Picanto", "ECAR"),
    ("Kia", "Rio", "ECAR"),
    ("Toyota", "Yaris", "ECAR"),
    ("Volkswagen", "Polo", "ECAR"),
    ("Dacia", "Sandero", "ECMR"),
    ("Fiat", "Panda", "MCMR"),
    ("Fiat", "500", "MCAR"),
    # Kompakt — CD**
    ("Fiat", "Egea", "CDAR"),
    ("Fiat", "Egea", "CDMR"),
    ("Fiat", "Egea", "CDAD"),
    ("Volkswagen", "Golf", "CDAR"),
    ("Ford", "Focus", "CDAR"),
    ("Hyundai", "Accent", "CDAR"),
    ("Renault", "Megane", "CDMR"),
    # Orta sedan — ID**
    ("Toyota", "Corolla", "IDAR"),
    ("Toyota", "Corolla", "IDMR"),
    ("Renault", "Megane Sedan", "IDAR"),
    ("Skoda", "Octavia", "IDAR"),
    # Standart — SD**
    ("Volkswagen", "Passat", "SDAR"),
    ("Volkswagen", "Passat", "SDMR"),
    ("Skoda", "Superb", "SDAR"),
    # Kompakt SUV — CF**
    ("Peugeot", "2008", "CFAR"),
    ("Opel", "Mokka", "CFAR"),
    ("Nissan", "Juke", "CFAR"),
    ("Hyundai", "Bayon", "CFAR"),
    ("Ford", "Puma", "CFAR"),
    ("Toyota", "C-HR", "CFAR"),
    ("Fiat", "Egea Cross", "CFAR"),
    # SUV — IF**
    ("Hyundai", "Tucson", "IFAR"),
    ("Hyundai", "Tucson", "IFMR"),
    ("Dacia", "Duster", "IFAR"),
    ("Peugeot", "3008", "IFAR"),
    ("Citroen", "C5 Aircross", "IFAR"),
    ("Seat", "Ateca", "IFAR"),
    # Ticari — FV**
    ("Ford", "Transit", "FVMR"),
    ("Ford", "Tourneo Courier", "FVMR"),
    ("Citroen", "Berlingo", "FVMR"),
    ("Peugeot", "Rifter", "FVMR"),
)
TELEMETRY_INTERVAL_SECONDS = 60  # one ping per minute of simulated driving


class Command(BaseCommand):
    help = "Seed SQLite (companies/vehicles) and ClickHouse (telemetry_logs) with demo data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--companies", type=int, default=DEFAULT_COMPANIES)
        parser.add_argument("--vehicles", type=int, default=DEFAULT_VEHICLES)
        parser.add_argument("--drivers", type=int, default=DEFAULT_DRIVERS)
        parser.add_argument("--logs-per-vehicle", type=int, default=DEFAULT_LOGS_PER_VEHICLE)
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing seeded data (companies/vehicles + telemetry) first.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Optional RNG seed for reproducible data.",
        )
        parser.add_argument(
            "--skip-telemetry",
            action="store_true",
            help="Seed only relational data; skip ClickHouse (useful when it is offline).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["seed"] is not None:
            random.seed(options["seed"])
            Faker.seed(options["seed"])

        faker = Faker("tr_TR")

        if options["flush"]:
            self._flush(skip_telemetry=options["skip_telemetry"])

        companies = self._seed_companies(faker, options["companies"])
        self._seed_users(companies[0])
        vehicles = self._seed_vehicles(faker, companies, options["vehicles"])
        drivers = self._seed_drivers(faker, companies[0], options["drivers"])
        self._seed_rentals(faker, drivers, vehicles)

        if options["skip_telemetry"]:
            self.stdout.write(self.style.WARNING("Skipping telemetry (ClickHouse) seeding."))
        else:
            self._seed_telemetry(vehicles, options["logs_per_vehicle"])

        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    # ------------------------------------------------------------------
    # Relational (SQLite) seeding
    # ------------------------------------------------------------------
    @transaction.atomic
    def _seed_companies(self, faker: Faker, count: int) -> list[Company]:
        self.stdout.write(f"Creating {count} companies...")
        companies = [
            Company(
                name=f"{faker.company()} Rent-a-Car",
                # Turkish tax numbers are 10 digits; uniqueness enforced by model.
                tax_number=faker.unique.numerify("##########"),
            )
            for _ in range(count)
        ]
        Company.objects.bulk_create(companies)
        # bulk_create on SQLite returns objects with PKs populated.
        return list(Company.objects.order_by("-id")[:count])

    @transaction.atomic
    def _seed_users(self, company: Company) -> None:
        """Demo kurumsal kullanıcılar (Filo Müdürü + Operasyon Personeli)."""
        self.stdout.write("Creating demo staff users...")
        demos = (
            {
                "username": "mudur",
                "password": "mudur123",
                "first_name": "Ahmet",
                "last_name": "Yılmaz",
                "role": UserRole.FLEET_MANAGER,
            },
            {
                "username": "operasyon",
                "password": "operasyon123",
                "first_name": "Elif",
                "last_name": "Kaya",
                "role": UserRole.OPERATIONS_STAFF,
            },
        )
        for spec in demos:
            user, created = CustomUser.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "role": spec["role"],
                    "company": company,
                },
            )
            if created:
                user.set_password(spec["password"])
                user.save()
                self.stdout.write(f"  + {spec['username']} ({spec['role']})")
            else:
                user.role = spec["role"]
                user.company = company
                user.set_password(spec["password"])
                user.save()
                self.stdout.write(f"  ~ {spec['username']} güncellendi")

    @transaction.atomic
    def _seed_vehicles(
        self, faker: Faker, companies: list[Company], count: int
    ) -> list[Vehicle]:
        self.stdout.write(f"Creating {count} vehicles (SIPP çeşitli filo)...")
        statuses = list(VehicleStatus.values)
        catalog = list(SEED_VEHICLE_CATALOG)
        vehicles: list[Vehicle] = []

        # Önce katalogdaki her SIPP'ten en az bir araç garanti et.
        for brand, model_name, sipp_code in catalog:
            if len(vehicles) >= count:
                break
            vehicles.append(self._build_vehicle(faker, companies, statuses, brand, model_name, sipp_code))

        # Kalan slotları katalogdan rastgele doldur.
        while len(vehicles) < count:
            brand, model_name, sipp_code = random.choice(catalog)
            vehicles.append(self._build_vehicle(faker, companies, statuses, brand, model_name, sipp_code))

        Vehicle.objects.bulk_create(vehicles)
        created = list(Vehicle.objects.order_by("-id")[:count])
        sipp_counts: dict[str, int] = {}
        for v in created:
            key = (v.sipp_code or "????")[:2]
            sipp_counts[key] = sipp_counts.get(key, 0) + 1
        self.stdout.write(f"  SIPP segment dağılımı: {dict(sorted(sipp_counts.items()))}")
        return created

    @staticmethod
    def _build_vehicle(
        faker: Faker,
        companies: list[Company],
        statuses: list[str],
        brand: str,
        model_name: str,
        sipp_code: str,
    ) -> Vehicle:
        return Vehicle(
            plate_number=Command._fake_plate(faker),
            brand=brand,
            model=model_name,
            sipp_code=sipp_code,
            production_year=random.randint(2015, 2025),
            current_km=random.randint(5_000, 250_000),
            status=random.choices(statuses, weights=(6, 3, 1), k=1)[0],
            company=random.choice(companies),
        )

    @transaction.atomic
    def _seed_drivers(self, faker: Faker, company: Company, count: int) -> list[Driver]:
        self.stdout.write(f"Creating {count} drivers...")
        genders = [Gender.MALE, Gender.FEMALE, Gender.OTHER]
        cities = ("Ankara", "İstanbul", "İzmir", "Bursa", "Antalya", "Konya")
        license_classes = ("B", "B", "B", "BE", "C")
        drivers: list[Driver] = []
        for _ in range(count):
            gender = random.choice(genders)
            if gender == Gender.MALE:
                first = faker.first_name_male()
            elif gender == Gender.FEMALE:
                first = faker.first_name_female()
            else:
                first = faker.first_name()
            drivers.append(
                Driver(
                    company=company,
                    first_name=first,
                    last_name=faker.last_name(),
                    national_id=faker.unique.numerify("###########"),
                    gender=gender,
                    birth_date=faker.date_of_birth(minimum_age=22, maximum_age=65),
                    phone=faker.numerify("05## ### ## ##"),
                    email=faker.email(),
                    license_number=faker.unique.bothify(text="??######"),
                    license_class=random.choice(license_classes),
                    city=random.choice(cities),
                    district=faker.city_suffix(),
                    address=faker.street_address()[:255],
                    is_blacklisted=random.random() < 0.03,
                )
            )
        Driver.objects.bulk_create(drivers)
        return list(Driver.objects.filter(company=company).order_by("-id")[:count])

    @transaction.atomic
    def _seed_rentals(
        self, faker: Faker, drivers: list[Driver], vehicles: list[Vehicle]
    ) -> None:
        """Kiralama kayıtları: kiradaki araçlara aktif, diğerlerine geçmiş kiralama."""
        self.stdout.write("Linking drivers to vehicles via rentals...")
        now = timezone.now()
        available_drivers = drivers.copy()
        random.shuffle(available_drivers)
        rentals: list[Rental] = []

        rented_vehicles = [v for v in vehicles if v.status == VehicleStatus.RENTED]
        for vehicle in rented_vehicles:
            if not available_drivers:
                break
            driver = available_drivers.pop()
            days_ago = random.randint(1, 14)
            start_km = max(0, vehicle.current_km - random.randint(200, 3_000))
            rentals.append(
                Rental(
                    driver=driver,
                    vehicle=vehicle,
                    status=RentalStatus.ACTIVE,
                    started_at=now - dt.timedelta(days=days_ago),
                    start_km=start_km,
                )
            )

        for vehicle in vehicles:
            if vehicle.status != VehicleStatus.AVAILABLE:
                continue
            if random.random() > 0.35 or not drivers:
                continue
            driver = random.choice(drivers)
            duration = random.randint(2, 10)
            ended_days_ago = random.randint(3, 45)
            end_at = now - dt.timedelta(days=ended_days_ago)
            start_at = end_at - dt.timedelta(days=duration)
            start_km = max(0, vehicle.current_km - random.randint(500, 8_000))
            rentals.append(
                Rental(
                    driver=driver,
                    vehicle=vehicle,
                    status=RentalStatus.COMPLETED,
                    started_at=start_at,
                    ended_at=end_at,
                    start_km=start_km,
                    end_km=vehicle.current_km - random.randint(0, 500),
                )
            )

        Rental.objects.bulk_create(rentals)
        self.stdout.write(f"  + {len(rentals)} rental records created")

    @staticmethod
    def _fake_plate(faker: Faker) -> str:
        """Generate a unique Turkish-style plate, e.g. '06 ABC 123'."""
        province = random.randint(1, 81)
        letters = "".join(random.choices("ABCDEFGHIJKLMNPRSTUVYZ", k=3))
        digits = faker.unique.numerify("###")
        return f"{province:02d} {letters} {digits}"

    # ------------------------------------------------------------------
    # Analytics (ClickHouse) seeding
    # ------------------------------------------------------------------
    def _seed_telemetry(self, vehicles: list[Vehicle], logs_per_vehicle: int) -> None:
        total = len(vehicles) * logs_per_vehicle
        self.stdout.write(
            f"Generating ~{total:,} telemetry logs for {len(vehicles)} vehicles "
            f"into ClickHouse table '{TELEMETRY_TABLE}'..."
        )

        try:
            with suppress_http_warnings():
                ensure_database()
                apply_schema()
                client = get_clickhouse_client()

                inserted = 0
                for batch in self._batched(self._all_trajectories(vehicles, logs_per_vehicle),
                                           CLICKHOUSE_INSERT_BATCH):
                    client.insert(
                        TELEMETRY_TABLE,
                        batch,
                        column_names=list(TELEMETRY_COLUMNS),
                    )
                    inserted += len(batch)
                    self.stdout.write(f"  inserted {inserted:,}/{total:,} rows", ending="\r")
        except OperationalError:
            # ClickHouse is unreachable (e.g. server down / connection refused
            # on port 8123). Relational seeding already succeeded, so we warn
            # and exit cleanly instead of crashing the whole command.
            self.stdout.write("")  # break out of the carriage-return line
            self.stdout.write(
                self.style.WARNING("ClickHouse not running, skipping telemetry insert")
            )
            return

        self.stdout.write("")  # newline after the progress carriage-returns
        self.stdout.write(self.style.SUCCESS(f"Inserted {inserted:,} telemetry rows."))

    def _all_trajectories(
        self, vehicles: list[Vehicle], logs_per_vehicle: int
    ) -> Iterator[tuple[Any, ...]]:
        """Yield telemetry rows for every vehicle, one coherent trajectory each."""
        for vehicle in vehicles:
            yield from self._build_vehicle_trajectory(vehicle, logs_per_vehicle)

    @staticmethod
    def _build_vehicle_trajectory(
        vehicle: Vehicle, log_count: int
    ) -> Iterator[tuple[Any, ...]]:
        """Generate a single vehicle's correlated telemetry as row tuples.

        Coordinates random-walk around Ankara, fuel drains while driving and
        refuels near empty, and speed varies enough to trigger violations and
        harsh-braking events.
        """
        device_id = vehicle.pk
        latitude, longitude = ANKARA_CENTER
        latitude += random.uniform(-0.05, 0.05)
        longitude += random.uniform(-0.05, 0.05)
        fuel_level = random.uniform(60.0, 100.0)
        # Each vehicle has its own comfortable cruising speed to revert toward.
        cruise_target = random.uniform(50.0, 85.0)
        previous_speed = cruise_target

        # Walk backwards in time so the newest ping is "now" (naive UTC, which
        # is what the ClickHouse DateTime column stores).
        now_utc = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        start_time = now_utc - dt.timedelta(seconds=log_count * TELEMETRY_INTERVAL_SECONDS)

        for step in range(log_count):
            timestamp = start_time + dt.timedelta(seconds=step * TELEMETRY_INTERVAL_SECONDS)

            # GPS random walk (~tens of meters per step).
            latitude += random.uniform(-0.0009, 0.0009)
            longitude += random.uniform(-0.0009, 0.0009)

            # Speed model: mostly mean-reverting toward the vehicle's cruise
            # target, with rare hard brakes and rare highway bursts. The bursts
            # are what occasionally breach the 120 km/h violation threshold.
            roll = random.random()
            if roll < 0.03:  # sudden hard deceleration -> harsh_brake
                speed = max(0.0, previous_speed - random.uniform(35.0, 60.0))
            elif roll < 0.06:  # highway burst, may exceed the limit
                speed = min(160.0, previous_speed + random.uniform(30.0, 55.0))
            else:  # normal cruising
                reversion = (cruise_target - previous_speed) * 0.2
                speed = max(0.0, min(160.0, previous_speed + reversion + random.uniform(-10.0, 10.0)))

            # Fuel drains with distance/speed; refuel when low.
            fuel_level -= speed * 0.0015 + random.uniform(0.0, 0.05)
            if fuel_level <= 5.0:
                fuel_level = random.uniform(90.0, 100.0)

            event_type = Command._classify_event(speed, previous_speed)
            previous_speed = speed

            yield (
                device_id,
                timestamp,
                round(speed, 2),
                round(max(0.0, fuel_level), 2),
                round(latitude, 6),
                round(longitude, 6),
                event_type,
            )

    @staticmethod
    def _classify_event(speed: float, previous_speed: float) -> str:
        """Derive an event_type from the speed profile (with some randomness)."""
        if speed > 120.0:
            return "speed_violation"
        if previous_speed - speed > 30.0:
            return "harsh_brake"
        if speed - previous_speed > 25.0:
            return "harsh_acceleration"
        # Rare random geofence breach to populate the category.
        if random.random() < 0.01:
            return "geofence_out"
        return "normal"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _batched(rows: Iterable[tuple[Any, ...]], size: int) -> Iterator[list[tuple[Any, ...]]]:
        """Chunk an iterable of rows into lists of at most ``size`` items."""
        batch: list[tuple[Any, ...]] = []
        for row in rows:
            batch.append(row)
            if len(batch) >= size:
                yield batch
                batch = []
        if batch:
            yield batch

    def _flush(self, skip_telemetry: bool = False) -> None:
        self.stdout.write(self.style.WARNING("Flushing existing seeded data..."))
        from backend.models import CompetitorPrice

        CompetitorPrice.objects.all().delete()
        Vehicle.objects.all().delete()
        Driver.objects.all().delete()
        CustomUser.objects.filter(
            username__in=("mudur", "operasyon"),
        ).delete()
        Company.objects.all().delete()
        if skip_telemetry:
            return
        try:
            with suppress_http_warnings():
                ensure_database()
                apply_schema()
                get_clickhouse_client().command(f"TRUNCATE TABLE IF EXISTS {TELEMETRY_TABLE}")
        except OperationalError:
            self.stdout.write(
                self.style.WARNING("ClickHouse not running, skipping telemetry flush")
            )
