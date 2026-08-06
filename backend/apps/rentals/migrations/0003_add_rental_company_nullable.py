from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_create_company_and_customuser"),
        ("rentals", "0002_alter_rental_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="rental",
            name="company",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="companies.company",
                verbose_name="company",
            ),
        ),
        migrations.AddIndex(
            model_name="rental",
            index=models.Index(fields=["company", "status"], name="rentals_company_status_idx"),
        ),
    ]
