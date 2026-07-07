# Generated manually for white-label Company branding fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_financial"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="display_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Arayüzde görünen ticari marka adı (white-label).",
                max_length=255,
                verbose_name="display name",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="logo_url",
            field=models.URLField(
                blank=True,
                help_text="Şirket logosu görsel adresi.",
                max_length=512,
                null=True,
                verbose_name="logo URL",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="primary_color",
            field=models.CharField(
                default="#3B82F6",
                help_text="Panel ana renk kodu (hex).",
                max_length=7,
                verbose_name="primary color",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="secondary_color",
            field=models.CharField(
                default="#1E3A8A",
                help_text="Menü / yan panel renk kodu (hex).",
                max_length=7,
                verbose_name="secondary color",
            ),
        ),
    ]
