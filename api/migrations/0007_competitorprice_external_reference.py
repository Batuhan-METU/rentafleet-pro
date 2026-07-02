"""CompetitorPrice: Enuygun referans kimliği ile benzersiz kayıt."""

from django.db import migrations, models
from django.db.models import Q


def clear_legacy_competitor_prices(apps, schema_editor) -> None:
    CompetitorPrice = apps.get_model("api", "CompetitorPrice")
    CompetitorPrice.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_competitorprice"),
    ]

    operations = [
        migrations.AddField(
            model_name="competitorprice",
            name="provider_name",
            field=models.CharField(
                blank=True,
                default="",
                max_length=64,
                verbose_name="provider name",
            ),
        ),
        migrations.AddField(
            model_name="competitorprice",
            name="external_reference",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=64,
                verbose_name="external reference",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="competitorprice",
            name="uniq_competitor_price_per_vehicle_source",
        ),
        migrations.AddConstraint(
            model_name="competitorprice",
            constraint=models.UniqueConstraint(
                condition=~Q(external_reference=""),
                fields=("vehicle", "external_reference"),
                name="uniq_competitor_price_vehicle_ext_ref",
            ),
        ),
        migrations.RunPython(clear_legacy_competitor_prices, migrations.RunPython.noop),
    ]
