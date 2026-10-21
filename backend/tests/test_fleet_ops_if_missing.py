"""fleet_ops seed --if-missing: boş veritabanını doldurur, dolu olana dokunmaz."""

from io import StringIO

import pytest
from django.core.management import call_command

from backend.apps.companies.models import CustomUser
from backend.apps.vehicles.models import Vehicle


def _seed_if_missing() -> str:
    out = StringIO()
    call_command(
        "fleet_ops",
        "seed",
        "--if-missing",
        "--i-know-this-is-not-prod",
        "--vehicles",
        "2",
        stdout=out,
    )
    return out.getvalue()


@pytest.mark.django_db
def test_if_missing_seeds_empty_database() -> None:
    output = _seed_if_missing()

    assert "White-label demo seed complete." in output
    assert CustomUser.objects.filter(username__in=["ahmet_mudur", "ercan_mudur"]).count() == 2
    assert CustomUser.objects.get(username="ahmet_mudur").check_password("ahmet123")


@pytest.mark.django_db
def test_if_missing_skips_when_already_seeded() -> None:
    _seed_if_missing()
    vehicle = Vehicle.objects.first()
    assert vehicle is not None
    vehicle.current_km = 123_456
    vehicle.save(update_fields=["current_km"])

    output = _seed_if_missing()

    assert "skipping" in output
    vehicle.refresh_from_db()
    assert vehicle.current_km == 123_456
