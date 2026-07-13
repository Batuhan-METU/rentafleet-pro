# Plaka benzersizliği platform genelinden şirket bazına taşındı (multi-tenant).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_company_description"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vehicle",
            name="plate_number",
            field=models.CharField(
                help_text="License plate; unique within the company.",
                max_length=16,
                verbose_name="plate number",
            ),
        ),
        migrations.AddConstraint(
            model_name="vehicle",
            constraint=models.UniqueConstraint(
                fields=("company", "plate_number"),
                name="uniq_vehicle_plate_per_company",
            ),
        ),
    ]
