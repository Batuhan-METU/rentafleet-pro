#!/usr/bin/env python3
"""Split monolithic backend/api/migrations/0001_initial.py into themed migration files."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

import django

django.setup()

from django.db import migrations, models
from django.db.migrations.writer import MigrationWriter

SRC = ROOT / "backend" / "api" / "migrations" / "0001_initial.py"
MIGRATIONS_DIR = ROOT / "backend" / "api" / "migrations"

spec = importlib.util.spec_from_file_location("migration_0001", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

all_ops: list = list(mod.Migration.operations)

VEHICLE_TCO_FIELDS = {
    "purchase_price",
    "initial_industrial_expense",
    "annual_kasko_cost",
    "annual_traffic_insurance_cost",
    "annual_insurance_cost",
    "annual_mtv_cost",
    "estimated_monthly_maintenance",
    "annual_inspection_cost",
    "fuel_tank_capacity_liters",
    "target_monthly_km",
}


def _model_name(op) -> str | None:
    if isinstance(op, migrations.CreateModel):
        return op.name.lower()
    if isinstance(op, migrations.AddField):
        return op.model_name
    if isinstance(op, migrations.AddIndex):
        return op.model_name
    if isinstance(op, migrations.AddConstraint):
        return op.model_name
    return None


def _strip_vehicle_tco(create_op: migrations.CreateModel) -> migrations.CreateModel:
    fields = [f for f in create_op.fields if f[0] not in VEHICLE_TCO_FIELDS]
    return migrations.CreateModel(
        name=create_op.name,
        fields=fields,
        options=create_op.options,
        bases=create_op.bases,
        managers=create_op.managers,
    )


def _vehicle_tco_add_fields(create_op: migrations.CreateModel) -> list:
    add_ops = []
    for name, field in create_op.fields:
        if name in VEHICLE_TCO_FIELDS:
            add_ops.append(migrations.AddField(model_name="vehicle", name=name, field=field))
    return add_ops


def _rental_with_vehicle(rental_op: migrations.CreateModel, vehicle_field) -> migrations.CreateModel:
    fields = list(rental_op.fields) + [("vehicle", vehicle_field)]
    return migrations.CreateModel(
        name=rental_op.name,
        fields=fields,
        options=rental_op.options,
        bases=rental_op.bases,
        managers=rental_op.managers,
    )


# Index operations by model
by_model: dict[str, list] = {}
create_ops: dict[str, migrations.CreateModel] = {}
add_field_ops: list = []

for op in all_ops:
    if isinstance(op, migrations.CreateModel):
        create_ops[op.name.lower()] = op
    elif isinstance(op, migrations.AddField):
        add_field_ops.append(op)
    else:
        name = _model_name(op)
        if name:
            by_model.setdefault(name, []).append(op)

vehicle_create = create_ops["vehicle"]
vehicle_core = _strip_vehicle_tco(vehicle_create)
vehicle_tco_fields = _vehicle_tco_add_fields(vehicle_create)

rental_vehicle_field = next(
    op.field for op in add_field_ops if op.model_name == "rental" and op.name == "vehicle"
)
rental_with_vehicle_op = _rental_with_vehicle(create_ops["rental"], rental_vehicle_field)

MIGRATION_PLANS = [
    {
        "filename": "0001_initial.py",
        "initial": True,
        "dependencies": [("auth", "0012_alter_user_first_name_max_length")],
        "operations": [
            create_ops["company"],
            create_ops["customuser"],
            vehicle_core,
            *by_model.get("vehicle", []),
        ],
    },
    {
        "filename": "0002_vehicle_live_state.py",
        "initial": False,
        "dependencies": [("api", "0001_initial")],
        "operations": [create_ops["vehiclelivestate"]],
    },
    {
        "filename": "0003_driver_rental.py",
        "initial": False,
        "dependencies": [("api", "0002_vehicle_live_state")],
        "operations": [
            create_ops["driver"],
            rental_with_vehicle_op,
            *by_model.get("driver", []),
            *by_model.get("rental", []),
        ],
    },
    {
        "filename": "0004_market_competitor.py",
        "initial": False,
        "dependencies": [("api", "0003_driver_rental")],
        "operations": [
            create_ops["enuygunmarketsnapshot"],
            create_ops["enuyguncachedreservation"],
            *by_model.get("enuyguncachedreservation", []),
            create_ops["competitorprice"],
            *by_model.get("competitorprice", []),
        ],
    },
    {
        "filename": "0005_financial.py",
        "initial": False,
        "dependencies": [("api", "0004_market_competitor")],
        "operations": [
            *vehicle_tco_fields,
            create_ops["vehiclefinancialprofile"],
            create_ops["vehicleexpense"],
            create_ops["rentalincome"],
            *by_model.get("rentalincome", []),
            *by_model.get("vehicleexpense", []),
        ],
    },
]


def write_migration(plan: dict) -> None:
    name = plan["filename"].replace(".py", "")

    class SplitMigration(migrations.Migration):
        initial = plan["initial"]
        dependencies = plan["dependencies"]
        operations = plan["operations"]

    writer = MigrationWriter(SplitMigration(name, "api"))
    content = writer.as_string()
    content = content.replace(
        f"class Migration(migrations.Migration):\n\n    dependencies = {plan['dependencies']!r}",
        f"class Migration(migrations.Migration):\n\n    initial = {plan['initial']!r}\n\n    dependencies = {plan['dependencies']!r}",
    )
    if plan["initial"]:
        # MigrationWriter already adds initial = True for first migration
        pass

    target = MIGRATIONS_DIR / plan["filename"]
    target.write_text(content)
    print(f"Wrote {target.name} ({len(plan['operations'])} operations)")


def main() -> None:
    backup = MIGRATIONS_DIR / "0001_initial.py.bak"
    if not backup.exists():
        backup.write_text(SRC.read_text())
        print(f"Backed up monolithic migration to {backup.name}")

    SRC.unlink()

    for plan in MIGRATION_PLANS:
        write_migration(plan)

    print("Done. Run: python manage.py makemigrations --check")


if __name__ == "__main__":
    main()
