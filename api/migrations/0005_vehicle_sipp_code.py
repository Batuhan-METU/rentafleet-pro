"""Araçlara SIPP kodu alanı ekler ve mevcut kayıtları doldurur."""

from __future__ import annotations

from django.db import migrations, models


def populate_sipp_codes(apps, schema_editor) -> None:
    Vehicle = apps.get_model("api", "Vehicle")
    # Migration sırasında servis import edilebilir; sadece statik harita kullanılır.
    from api.services.sipp_service import resolve_sipp

    for vehicle in Vehicle.objects.all():
        profile = resolve_sipp(vehicle.brand, vehicle.model, None)
        vehicle.sipp_code = profile.code
        vehicle.save(update_fields=["sipp_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_driver_rental_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="sipp_code",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="ACRISS/SIPP 4 harfli kiralama sınıf kodu (ör. ECMR).",
                max_length=4,
                verbose_name="SIPP code",
            ),
        ),
        migrations.RunPython(populate_sipp_codes, migrations.RunPython.noop),
    ]
