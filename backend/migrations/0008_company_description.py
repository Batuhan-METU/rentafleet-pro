# Generated manually for company description field.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0007_decision_support"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Genel bakış ve ayarlar ekranında gösterilen şirket tanıtımı.",
                verbose_name="company description",
            ),
        ),
    ]
