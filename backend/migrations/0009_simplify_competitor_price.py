# CompetitorPrice sadeleştirme — gereksiz alanlar kaldırıldı (uygulandı: 0009)

from django.db import migrations, models


def deduplicate_competitor_prices(apps, schema_editor):
    CompetitorPrice = apps.get_model("api", "CompetitorPrice")
    seen: set[tuple[int, str, object, object]] = set()
    to_delete: list[int] = []

    for row in CompetitorPrice.objects.order_by(
        "vehicle_id",
        "source_name",
        "pickup_date",
        "dropoff_date",
        "daily_price",
        "id",
    ):
        key = (row.vehicle_id, row.source_name, row.pickup_date, row.dropoff_date)
        if key in seen:
            to_delete.append(row.pk)
        else:
            seen.add(key)

    if to_delete:
        CompetitorPrice.objects.filter(pk__in=to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_company_description"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="competitorprice",
            name="uniq_competitor_price_vehicle_ext_ref_window",
        ),
        migrations.RemoveField(model_name="competitorprice", name="provider_name"),
        migrations.RemoveField(model_name="competitorprice", name="external_reference"),
        migrations.RemoveField(model_name="competitorprice", name="similar_vehicle"),
        migrations.RemoveField(model_name="competitorprice", name="updated_at"),
        migrations.RemoveField(model_name="competitorprice", name="created_at"),
        migrations.RunPython(deduplicate_competitor_prices, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="competitorprice",
            constraint=models.UniqueConstraint(
                fields=("vehicle", "source_name", "pickup_date", "dropoff_date"),
                name="uniq_competitor_price_vehicle_source_window",
            ),
        ),
    ]
