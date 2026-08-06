"""Şirket geneli gider (§3.3) için KÜÇÜK, AÇIKÇA GÖSTERGE NİTELİĞİNDE bir
aylık seti üretir — personel/kira/elektrik-su gibi araca özel olmayan
giderler, filo büyüklüğüyle orantılı kaba bir tahminle.

Bu, plandaki TEK "gerçek veriye dayanmayan" adımdır: ZiraatFilo'nun ham
muhasebe defteri (Faaliyet_Giderleri*.xlsx) kendi 22.000 araçlık filosuna
özgü ve anonimleştirilmiş/ölçeklenmiş (bkz. MALIYET_HESAPLAMA_METODOLOJISI
§11) — bizim küçük yerel şirketlerimize doğrudan eşlenebilir bir kaynak
değil. Bu komut sadece motorun §3.3 bileşenini "None" durumundan çıkarmak
için makul bir taban sağlar; gerçek muhasebe verisi elde edilince mevcut
``import_overhead_expenses`` (CSV, idempotent) ile üzerine yazılabilir.

Kullanım::

    python manage.py seed_overhead_expenses --company-id 53 \\
        --monthly-total 175000 --months 6
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import CompanyOverheadExpense

# Aylık toplamın kategori kırılımı — Faaliyet_Giderleri*.xlsx'teki ağırlıklı
# gider kalemlerinden (PERSONEL BRÜT ÜCRET, KİRA, ELEKTRİK/SU) esinlenilmiştir.
CATEGORY_SPLIT = {
    "Personel": Decimal("0.70"),
    "Kira": Decimal("0.20"),
    "Elektrik/Su": Decimal("0.10"),
}


class Command(BaseCommand):
    help = "Şirket geneli genel gideri (personel/kira/elektrik-su) küçük, gösterge niteliğinde seedler."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--company-id", type=int, required=True, help="Hedef şirket ID.")
        parser.add_argument(
            "--monthly-total", type=Decimal, required=True, help="Aylık toplam genel gider (TL)."
        )
        parser.add_argument(
            "--months", type=int, default=6, help="Kaç ay geriye dönük seedlenecek (varsayılan 6)."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Hiçbir şey kaydetmeden özet göster."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            company = Company.objects.get(pk=options["company_id"])
        except Company.DoesNotExist as exc:
            raise CommandError(f"Şirket bulunamadı: id={options['company_id']}") from exc

        monthly_total: Decimal = options["monthly_total"]
        months: int = options["months"]
        today = date.today()

        rows: list[CompanyOverheadExpense] = []
        for month_offset in range(months):
            # Takvim ayı hassasiyeti gerekmiyor (günlük dağıtım zaten §3.3'te
            # fiyat ağırlıklı yapılıyor) — bugünden geriye 30 günlük bloklar.
            block_end = today - timedelta(days=30 * month_offset)
            block_start = block_end - timedelta(days=29)
            daily_amount = (monthly_total / 30).quantize(Decimal("0.01"))
            for day_offset in range(30):
                expense_date = block_start + timedelta(days=day_offset)
                if expense_date > today:
                    continue
                for category, ratio in CATEGORY_SPLIT.items():
                    rows.append(
                        CompanyOverheadExpense(
                            company=company,
                            expense_date=expense_date,
                            amount=(daily_amount * ratio).quantize(Decimal("0.01")),
                            category=category,
                            source_note="Gösterge niteliğinde tahmini genel gider (seed_overhead_expenses)",
                        )
                    )

        self.stdout.write(
            f"{company.name}: {len(rows)} satır ({months} ay, günlük ~{(monthly_total/30):.2f} TL/gün)."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: hiçbir şey kaydedilmedi."))
            return

        with transaction.atomic():
            CompanyOverheadExpense.objects.bulk_create(rows, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"{len(rows)} genel gider satırı oluşturuldu."))
