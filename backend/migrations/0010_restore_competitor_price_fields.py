# 0009_simplify_competitor_price geri alındı — CompetitorPrice alanları restore

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_simplify_competitor_price"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="competitorprice",
            name="uniq_competitor_price_vehicle_source_window",
        ),
        migrations.AddField(
            model_name="competitorprice",
            name="provider_name",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="provider name"),
        ),
        migrations.AddField(
            model_name="competitorprice",
            name="external_reference",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64, verbose_name="external reference"),
        ),
        migrations.AddField(
            model_name="competitorprice",
            name="similar_vehicle",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Piyasada eşleştirilen benzer araç (ör. Fiat Egea).",
                max_length=128,
                verbose_name="similar vehicle",
            ),
        ),
        migrations.AddField(
            model_name="competitorprice",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now, verbose_name="updated at"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="competitorprice",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="created at",
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="competitorprice",
            constraint=models.UniqueConstraint(
                condition=models.Q(("external_reference", ""), _negated=True),
                fields=("vehicle", "external_reference", "pickup_date", "dropoff_date"),
                name="uniq_competitor_price_vehicle_ext_ref_window",
            ),
        ),
    ]
