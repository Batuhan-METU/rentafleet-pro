"""Genel gider (§3.3) CSV import — muhasebeden gelen gerçek veriyi
``CompanyOverheadExpense``'e yükler.

Beklenen CSV kolonları: ``date`` (YYYY-MM-DD), ``amount``, ``category``
(opsiyonel). Hatalı/eksik satırlar SESSİZCE ATLANMAZ — satır numarası ve
sebebiyle raporlanır (§1.5 "Bilinmiyor ≠ Sıfır" ilkesi: sessiz veri kaybı
istenmez). Aynı (şirket, tarih, kategori) için tekrar import ``update_or_create``
ile üzerine yazar — idempotenttir.

Kullanım::

    python manage.py import_overhead_expenses giderler.csv --company-id 1
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import CompanyOverheadExpense

REQUIRED_COLUMNS = {"date", "amount"}


class Command(BaseCommand):
    help = "Genel gider CSV'sini bir şirkete import eder (kolonlar: date, amount, [category])."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("csv_path", type=str, help="CSV dosya yolu.")
        parser.add_argument("--company-id", type=int, required=True, help="Hedef şirket ID.")
        parser.add_argument(
            "--source-note",
            type=str,
            default="",
            help="Kaynak notu (ör. '2026-03 muhasebe importu').",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            company = Company.objects.get(pk=options["company_id"])
        except Company.DoesNotExist as exc:
            raise CommandError(f"Şirket bulunamadı: id={options['company_id']}") from exc

        csv_path: str = options["csv_path"]
        source_note: str = options["source_note"]

        try:
            file_handle = open(csv_path, newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(f"Dosya okunamadı: {csv_path} ({exc})") from exc

        created = 0
        updated = 0
        errors: list[str] = []

        with file_handle:
            reader = csv.DictReader(file_handle)
            found_columns = {(field or "").strip().lower() for field in (reader.fieldnames or [])}
            if not REQUIRED_COLUMNS.issubset(found_columns):
                raise CommandError(
                    f"CSV kolonları eksik. Gerekli: {sorted(REQUIRED_COLUMNS)}, "
                    f"bulunan: {reader.fieldnames}"
                )

            for line_no, raw_row in enumerate(reader, start=2):  # satır 1 = başlık
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items()}

                try:
                    expense_date = date.fromisoformat(row.get("date", ""))
                except ValueError:
                    errors.append(f"Satır {line_no}: geçersiz tarih '{row.get('date', '')}'")
                    continue

                try:
                    amount = Decimal(row.get("amount", ""))
                except InvalidOperation:
                    errors.append(f"Satır {line_no}: geçersiz tutar '{row.get('amount', '')}'")
                    continue

                category = row.get("category", "")
                _, was_created = CompanyOverheadExpense.objects.update_or_create(
                    company=company,
                    expense_date=expense_date,
                    category=category,
                    defaults={"amount": amount, "source_note": source_note},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(f"{created} yeni, {updated} güncellenen kayıt."))
        if errors:
            self.stdout.write(self.style.WARNING(f"{len(errors)} satır atlandı:"))
            for error in errors:
                self.stdout.write(f"  - {error}")
