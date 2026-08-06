from django.db import migrations, models
import django.db.models.deletion


def backfill_rental_company(apps, schema_editor):
    Rental = apps.get_model("rentals", "Rental")
    # Küçük/orta veri hacmi için basit ve KESİN doğru yol: driver.company_id'yi
    # oku, bulk_update ile yaz. Çapraz-ilişki F() ifadesiyle tek sorguda
    # UPDATE etmek yerine bilerek bu yol seçildi — backend'ler arası (SQLite/
    # Postgres) F()+JOIN update davranışı tutarsız olabilir, bu script bir
    # kerelik migration'da çalışır, performans kritik değildir.
    rentals = list(
        Rental.objects.filter(company__isnull=True).select_related("driver")
    )
    for rental in rentals:
        rental.company_id = rental.driver.company_id
    Rental.objects.bulk_update(rentals, ["company_id"], batch_size=500)


def noop_reverse(apps, schema_editor):
    # Geri alma, sütunu NULL'a döndürmekten (bir sonraki migration'ın
    # RemoveField/AlterField'i zaten yapar) başka bir şey gerektirmiyor.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("rentals", "0003_add_rental_company_nullable"),
    ]

    operations = [
        migrations.RunPython(backfill_rental_company, noop_reverse),
        migrations.AlterField(
            model_name="rental",
            name="company",
            field=models.ForeignKey(
                help_text=(
                    "driver.company'nin denormalize kopyası — kiracı-kapsamlı sorgular "
                    "(bkz. _rental_queryset/get_scoped_rental) driver üzerinden JOIN "
                    "yapmadan doğrudan filtreleyebilsin diye. save() tarafından "
                    "otomatik doldurulur, elle ayarlamaya gerek yoktur."
                ),
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="companies.company",
                verbose_name="company",
            ),
        ),
    ]
