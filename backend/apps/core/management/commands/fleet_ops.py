"""Fleet operations CLI — white-label demo seeding.

Usage::

    python manage.py fleet_ops seed
    python manage.py fleet_ops seed --flush
    python manage.py fleet_ops seed --vehicles 30

Seeds two FIXED, branded demo tenants (Ahmet Rent A Car / Ercan Rent A Car)
with real login credentials and named drivers — for sales/UI demos, not
volume testing. For randomized bulk data (N companies/vehicles + ClickHouse
telemetry), use ``manage.py seed_data`` instead (see that command's
docstring); this command imports its ``SEED_VEHICLE_CATALOG`` so both stay
in sync on vehicle data.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from backend.apps.companies.models import (
    Company,
    CustomUser,
    UserRole,
)
from backend.apps.core.management.commands.seed_data import SEED_VEHICLE_CATALOG
from backend.apps.customer_profiles.models import (
    Driver,
    Gender,
)
from backend.apps.vehicle_finance.models import VehicleFinancialProfile
from backend.apps.vehicles.models import (
    FuelType,
    Transmission,
    Vehicle,
    VehicleCondition,
    VehicleStatus,
)

DEFAULT_VEHICLES_PER_TENANT = 25

TENANT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "slug": "ahmet",
        "display_name": "Ahmet Rent A Car",
        "tax_number": "1000000001",
        "primary_color": "#FF5733",
        "secondary_color": "#2C3E50",
        "logo_url": "https://ui-avatars.com/api/?name=Ahmet+Rent&background=FF5733&color=fff&size=128&bold=true",
        "plate_prefix": "34 ARC",
        "manager": {
            "username": "ahmet_mudur",
            "password": "ahmet123",
            "first_name": "Ahmet",
            "last_name": "Demir",
        },
        "drivers": (
            ("11111111110", "Mehmet", "Yıldız", Gender.MALE),
            ("11111111111", "Ayşe", "Çelik", Gender.FEMALE),
            ("11111111112", "Can", "Öztürk", Gender.MALE),
            ("11111111113", "Deniz", "Kara", Gender.FEMALE),
            ("11111111114", "Selin", "Akın", Gender.FEMALE),
            ("11111111115", "Oğuz", "Polat", Gender.MALE),
        ),
    },
    {
        "slug": "ercan",
        "display_name": "Ercan Rent A Car",
        "tax_number": "2000000002",
        "primary_color": "#00b4d8",
        "secondary_color": "#03045e",
        "logo_url": "https://ui-avatars.com/api/?name=Ercan+Rent&background=00b4d8&color=fff&size=128&bold=true",
        "plate_prefix": "06 ERC",
        "manager": {
            "username": "ercan_mudur",
            "password": "ercan123",
            "first_name": "Ercan",
            "last_name": "Koç",
        },
        "drivers": (
            ("22222222220", "Burak", "Aydın", Gender.MALE),
            ("22222222221", "Zeynep", "Arslan", Gender.FEMALE),
            ("22222222222", "Emre", "Şahin", Gender.MALE),
            ("22222222223", "Merve", "Yalçın", Gender.FEMALE),
            ("22222222224", "Kaan", "Demirtaş", Gender.MALE),
            ("22222222225", "Ece", "Güneş", Gender.FEMALE),
        ),
    },
)

_SELLERS = (
    "Otokoç",
    "Borusan Otomotiv",
    "Doğuş Oto",
    "İkinci El Galeri",
    "Yetkili Bayi",
    "Filo İhalesi",
)


def _money(amount: float | int) -> Decimal:
    return Decimal(str(round(float(amount), 2)))


def _fuel_type_from_sipp(sipp: str) -> str:
    fuel_code = (sipp or "????").upper().ljust(4, "?")[3]
    if fuel_code in ("D", "Q"):
        return FuelType.DIESEL
    if fuel_code in ("E", "C"):
        return FuelType.ELECTRIC
    if fuel_code in ("H", "I", "M"):
        return FuelType.HYBRID
    if fuel_code in ("L", "S"):
        return FuelType.LPG
    return FuelType.GASOLINE


def _transmission_from_sipp(sipp: str) -> str:
    trans_code = (sipp or "????").upper().ljust(4, "?")[2]
    if trans_code in ("M", "N", "C"):
        return Transmission.MANUAL
    return Transmission.AUTOMATIC


def _tank_liters(sipp: str) -> float:
    body = (sipp or "????").upper().ljust(4, "?")[1]
    if body in ("V", "M"):
        return 70.0
    if body == "F":
        return 55.0
    if body == "P":
        return 80.0
    return 45.0


def _base_purchase_price(sipp: str, production_year: int) -> Decimal:
    category = (sipp or "CDMR").upper()[0]
    base_by_category = {
        "M": 520_000,
        "E": 580_000,
        "C": 720_000,
        "I": 950_000,
        "S": 1_100_000,
        "F": 1_450_000,
        "P": 1_800_000,
        "L": 2_200_000,
        "X": 900_000,
    }
    base = base_by_category.get(category, 750_000)
    age = max(0, date.today().year - production_year)
    depreciation = age * random.randint(45_000, 75_000)
    jitter = random.randint(-35_000, 55_000)
    return _money(max(320_000, base - depreciation + jitter))


def _daily_price_band(sipp: str) -> tuple[Decimal, Decimal, Decimal]:
    category = (sipp or "CDMR").upper()[0]
    bands = {
        "M": (650, 850, 1_050),
        "E": (750, 950, 1_150),
        "C": (900, 1_200, 1_550),
        "I": (1_100, 1_450, 1_850),
        "S": (1_300, 1_700, 2_200),
        "F": (1_500, 1_950, 2_500),
        "P": (1_800, 2_300, 2_900),
    }
    low, mid, high = bands.get(category, (900, 1_200, 1_600))
    spread = random.uniform(0.92, 1.08)
    return (
        _money(low * spread),
        _money(mid * spread),
        _money(high * spread),
    )


def _vehicle_cost_fields(sipp: str, production_year: int, current_km: int) -> dict[str, Any]:
    purchase = _base_purchase_price(sipp, production_year)
    return {
        "purchase_price": purchase,
        "initial_industrial_expense": _money(random.randint(8_000, 28_000)),
        "annual_kasko_cost": _money(float(purchase) * random.uniform(0.030, 0.042)),
        "annual_traffic_insurance_cost": _money(float(purchase) * random.uniform(0.010, 0.016)),
        "annual_mtv_cost": _money(float(purchase) * random.uniform(0.008, 0.014)),
        "estimated_monthly_maintenance": _money(random.randint(1_800, 3_400)),
        "annual_inspection_cost": _money(random.randint(2_200, 4_800)),
        "fuel_tank_capacity_liters": _money(_tank_liters(sipp)),
        "fuel_type": _fuel_type_from_sipp(sipp),
        "transmission": _transmission_from_sipp(sipp),
        "target_monthly_km": random.randint(3_000, 5_500),
    }


def _financial_profile_defaults(vehicle: Vehicle) -> dict[str, Any]:
    sipp = vehicle.sipp_code or "CDMR"
    min_price, target_price, max_price = _daily_price_band(sipp)
    purchase = vehicle.purchase_price or _base_purchase_price(sipp, vehicle.production_year)
    purchase_date = date(vehicle.production_year, random.randint(1, 12), random.randint(1, 28))
    if purchase_date > date.today():
        purchase_date = date.today() - timedelta(days=random.randint(90, 900))

    planned_years = Decimal(str(round(random.uniform(2.0, 4.5), 1)))
    expected_sale_date = purchase_date + timedelta(days=int(float(planned_years) * 365))
    expected_sale_km = vehicle.current_km + random.randint(60_000, 140_000)
    residual = float(purchase) * random.uniform(0.42, 0.62)

    return {
        "purchase_date": purchase_date,
        "purchase_price": purchase,
        "seller_name": random.choice(_SELLERS),
        "condition": (
            VehicleCondition.NEW
            if vehicle.production_year >= date.today().year - 1
            else VehicleCondition.USED
        ),
        "purchase_km": max(0, vehicle.current_km - random.randint(3_000, 45_000)),
        "inspection_result": random.choice(
            ("Ekspertiz temiz", "Hafif boya", "Tramer kaydı yok", "Periyodik bakımlı")
        ),
        "notes": "Demo seed — otomatik maliyet profili",
        "min_daily_price": min_price,
        "target_daily_price": target_price,
        "max_daily_price": max_price,
        "delivery_location": random.choice(("Ankara Merkez", "Esenboğa Havalimanı", "Çankaya Şube")),
        "daily_km_limit": random.choice((250, 300, 400)),
        "monthly_km_limit": random.choice((4_000, 5_000, 6_000)),
        "planned_years_in_fleet": planned_years,
        "expected_sale_date": expected_sale_date,
        "expected_sale_km": expected_sale_km,
        "expected_sale_price": _money(residual),
    }


class Command(BaseCommand):
    help = "Fleet operations: white-label demo tenants (ahmet / ercan)."

    def add_arguments(self, parser: CommandParser) -> None:
        subparsers = parser.add_subparsers(dest="action", required=True)
        seed_parser = subparsers.add_parser(
            "seed",
            help="Ahmet ve Ercan Rent A Car test kiracılarını oluşturur.",
        )
        seed_parser.add_argument(
            "--flush",
            action="store_true",
            help="Mevcut ahmet/ercan kiracı verilerini silip yeniden oluşturur.",
        )
        seed_parser.add_argument(
            "--vehicles",
            type=int,
            default=DEFAULT_VEHICLES_PER_TENANT,
            help=f"Kiracı başına araç sayısı (varsayılan: {DEFAULT_VEHICLES_PER_TENANT}).",
        )
        seed_parser.add_argument(
            "--if-missing",
            action="store_true",
            help=(
                "Demo yönetici hesaplarının hepsi zaten varsa hiçbir şey yapma. "
                "Sunucu açılış komutunda güvenle çalıştırılabilmesi içindir: "
                "boş bir veritabanını doldurur, mevcut demo verisine dokunmaz."
            ),
        )
        seed_parser.add_argument(
            "--i-know-this-is-not-prod",
            action="store_true",
            help=(
                "DEBUG=False iken de zorla çalıştır. Bu komut TENANT_SPECS içinde "
                "sabit kodlanmış zayıf şifrelerle (ör. 'ahmet123') gerçek giriş "
                "hesapları oluşturur — bir üretim veritabanına karşı yanlışlıkla "
                "çalıştırılmasını önlemek için varsayılan olarak DEBUG=True gerektirir."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not options.get("i_know_this_is_not_prod"):
            raise CommandError(
                "fleet_ops seed, sabit/zayıf demo şifreleri oluşturduğu için DEBUG=False "
                "iken varsayılan olarak reddedilir. Bunun bir üretim veritabanı OLMADIĞINDAN "
                "eminseniz --i-know-this-is-not-prod ile tekrar çalıştırın."
            )
        if options.get("action") == "seed":
            if options.get("if_missing"):
                usernames = [spec["manager"]["username"] for spec in TENANT_SPECS]
                existing = CustomUser.objects.filter(username__in=usernames).count()
                if existing == len(usernames):
                    self.stdout.write("Demo tenants already seeded; skipping (--if-missing).")
                    return
            self._run_seed(
                flush=bool(options.get("flush")),
                vehicles_per_tenant=int(options["vehicles"]),
            )

    @transaction.atomic
    def _run_seed(self, *, flush: bool, vehicles_per_tenant: int) -> None:
        slugs = [spec["slug"] for spec in TENANT_SPECS]
        if flush:
            self.stdout.write("Flushing ahmet / ercan tenants...")
            Company.objects.filter(name__in=slugs).delete()

        for spec in TENANT_SPECS:
            self._seed_tenant(spec, vehicles_per_tenant=vehicles_per_tenant)

        self.stdout.write(self.style.SUCCESS("White-label demo seed complete."))
        self.stdout.write("  ahmet.localhost → ahmet_mudur / ahmet123")
        self.stdout.write("  ercan.localhost → ercan_mudur / ercan123")

    def _seed_tenant(self, spec: dict[str, Any], *, vehicles_per_tenant: int) -> None:
        company, created = Company.objects.update_or_create(
            name=spec["slug"],
            defaults={
                "tax_number": spec["tax_number"],
                "display_name": spec["display_name"],
                "logo_url": spec["logo_url"],
                "primary_color": spec["primary_color"],
                "secondary_color": spec["secondary_color"],
            },
        )
        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} tenant: {company.display_name} ({company.name})")

        manager_spec = spec["manager"]
        manager, mgr_created = CustomUser.objects.get_or_create(
            username=manager_spec["username"],
            defaults={
                "first_name": manager_spec["first_name"],
                "last_name": manager_spec["last_name"],
                "role": UserRole.FLEET_MANAGER,
                "company": company,
            },
        )
        manager.first_name = manager_spec["first_name"]
        manager.last_name = manager_spec["last_name"]
        manager.role = UserRole.FLEET_MANAGER
        manager.company = company
        manager.set_password(manager_spec["password"])
        manager.save()
        self.stdout.write(f"  Manager: {manager.username} ({'new' if mgr_created else 'updated'})")

        catalog = list(SEED_VEHICLE_CATALOG)
        statuses = [
            VehicleStatus.AVAILABLE,
            VehicleStatus.RENTED,
            VehicleStatus.MAINTENANCE,
        ]
        status_weights = (6, 3, 1)  # available, rented, maintenance
        plate_prefix = spec["plate_prefix"]

        for index in range(1, vehicles_per_tenant + 1):
            brand, model, sipp = catalog[(index - 1) % len(catalog)]
            plate = f"{plate_prefix} {index:02d}"
            production_year = random.randint(2019, 2024)
            current_km = random.randint(8_000, 120_000)
            status = random.choices(statuses, weights=status_weights, k=1)[0]
            cost_fields = _vehicle_cost_fields(sipp, production_year, current_km)

            vehicle, _ = Vehicle.objects.update_or_create(
                plate_number=plate,
                defaults={
                    "company": company,
                    "brand": brand,
                    "model": model,
                    "sipp_code": sipp,
                    "production_year": production_year,
                    "current_km": current_km,
                    "status": status,
                    **cost_fields,
                },
            )
            VehicleFinancialProfile.objects.update_or_create(
                vehicle=vehicle,
                defaults=_financial_profile_defaults(vehicle),
            )

        expected_plates = {f"{plate_prefix} {index:02d}" for index in range(1, vehicles_per_tenant + 1)}
        removed = (
            Vehicle.objects.filter(company=company)
            .exclude(plate_number__in=expected_plates)
            .delete()[0]
        )
        if removed:
            self.stdout.write(f"  Removed {removed} legacy vehicle(s) outside demo plate range")

        self.stdout.write(
            f"  Vehicles: {vehicles_per_tenant} (maliyet + finans profili dolu)"
        )

        for national_id, first_name, last_name, gender in spec["drivers"]:
            Driver.objects.update_or_create(
                national_id=national_id,
                defaults={
                    "company": company,
                    "first_name": first_name,
                    "last_name": last_name,
                    "gender": gender,
                    "birth_date": "1990-05-15",
                    "phone": "05" + national_id[-9:],
                    "license_number": f"TR{national_id[-6:]}",
                    "city": "Ankara",
                },
            )
        self.stdout.write(f"  Drivers: {len(spec['drivers'])}")