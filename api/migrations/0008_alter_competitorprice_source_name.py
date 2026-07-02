from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_competitorprice_external_reference"),
    ]

    operations = [
        migrations.AlterField(
            model_name="competitorprice",
            name="source_name",
            field=models.CharField(
                help_text="Örn. Avis, Sixt, Garenta",
                max_length=128,
                verbose_name="source name",
            ),
        ),
    ]
