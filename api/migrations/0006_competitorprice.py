# Generated migration for CompetitorPrice model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_vehicle_sipp_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitorPrice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "sipp_code",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=4,
                        verbose_name="SIPP code",
                    ),
                ),
                (
                    "source_name",
                    models.CharField(
                        help_text="Örn. Avis, Sixt, Garenta",
                        max_length=64,
                        verbose_name="source name",
                    ),
                ),
                (
                    "daily_price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=10,
                        verbose_name="daily price",
                    ),
                ),
                (
                    "similar_vehicle",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Piyasada eşleştirilen benzer araç (ör. Fiat Egea).",
                        max_length=128,
                        verbose_name="similar vehicle",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="updated at"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="created at"),
                ),
                (
                    "vehicle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="competitor_prices",
                        to="api.vehicle",
                        verbose_name="vehicle",
                    ),
                ),
            ],
            options={
                "verbose_name": "competitor price",
                "verbose_name_plural": "competitor prices",
                "ordering": ("source_name",),
            },
        ),
        migrations.AddIndex(
            model_name="competitorprice",
            index=models.Index(
                fields=["vehicle", "sipp_code"],
                name="api_competi_vehicle_6be2c9_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="competitorprice",
            constraint=models.UniqueConstraint(
                fields=("vehicle", "source_name"),
                name="uniq_competitor_price_per_vehicle_source",
            ),
        ),
    ]
