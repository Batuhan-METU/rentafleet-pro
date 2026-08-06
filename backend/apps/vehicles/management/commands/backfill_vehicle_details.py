"""Tek seferlik veri düzeltmesi — `import_fleet_vehicles` ile daha önce
aktarılmış araçlarda eksik kalan üç alanı doldurur:

1. ``model``/``package`` ayrımı — ilk import, kaynağın birleşik
   "Model - Donanım" sütununu (ör. "208 ACTIVE DYNAMIC 1.5 BLUEHDI 100
   S&S") tamamen ``model``'e yazmıştı. İlk kelime modele, kalanı
   ``package``'a taşınır (Excel'e ihtiyaç yok — mevcut ``model`` alanı
   zaten kaynak).
2. ``branch_name`` — kaynağın "Şube" sütunu hiç aktarılmamıştı; plaka
   eşleştirmesiyle Excel'den geri doldurulur.
3. ``purchase_invoice_date`` — kaynağın "Satın Alma (Fatura) Tarihi"
   sütunu da aktarılmamıştı; aynı şekilde plaka eşleştirmesiyle doldurulur.

Sadece boş olan alanlar güncellenir; zaten dolu olan ``package`` gibi
alanlara dokunulmaz. Plaka Excel'de bulunamayan araçlar (2 ve 3 için)
sessizce atlanır.

Kullanım::

    python manage.py backfill_vehicle_details ../datas/Vehicle_duzeltilmis.xlsx
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from backend.apps.vehicles.models import Vehicle

COL_PLATE = "Plaka"
COL_BRANCH = "Şube"
COL_PURCHASE_INVOICE_DATE = "Satın Alma (Fatura) Tarihi"


def _parse_turkish_date(raw: object) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not raw:
        return None
    text = str(raw).strip().split(" ")[0]
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Daha önce import edilmiş araçlarda model/donanım ayrımını ve şube/fatura tarihini doldurur."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("xlsx_path", type=str, help="Kaynak .xlsx dosya yolu.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hiçbir şey kaydetmeden neyin değişeceğini göster.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError("openpyxl kurulu değil (pip install openpyxl).") from exc

        xlsx_path: str = options["xlsx_path"]
        try:
            workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        except (OSError, KeyError) as exc:
            raise CommandError(f"Dosya okunamadı: {xlsx_path} ({exc})") from exc

        sheet = workbook[workbook.sheetnames[0]]
        rows_iter = sheet.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
        for required in (COL_PLATE, COL_BRANCH, COL_PURCHASE_INVOICE_DATE):
            if required not in header:
                raise CommandError(f"Eksik sütun: {required}")

        by_plate: dict[str, dict[str, object]] = {}
        for row in rows_iter:
            record = dict(zip(header, row))
            plate = str(record.get(COL_PLATE) or "").strip()
            if plate:
                by_plate[plate] = record

        self.stdout.write(f"Kaynakta {len(by_plate)} benzersiz plaka bulundu.")

        # --- 1) model/donanım ayrımı — yalnızca mevcut DB verisiyle -----
        model_fix_count = 0
        vehicles_needing_split = list(
            Vehicle.objects.exclude(model="").filter(package="")
        )
        for vehicle in vehicles_needing_split:
            parts = vehicle.model.split(maxsplit=1)
            if len(parts) < 2:
                continue
            vehicle.model = parts[0][:64]
            vehicle.package = parts[1][:64]
            model_fix_count += 1

        # --- 2) şube + fatura tarihi — plaka eşleştirmesiyle Excel'den ---
        branch_fix_count = 0
        invoice_date_fix_count = 0
        unmatched_plates: list[str] = []
        all_vehicles = list(Vehicle.objects.all())
        for vehicle in all_vehicles:
            source = by_plate.get(vehicle.plate_number)
            if source is None:
                if not vehicle.branch_name and vehicle.purchase_invoice_date is None:
                    unmatched_plates.append(vehicle.plate_number)
                continue
            if not vehicle.branch_name:
                branch = str(source.get(COL_BRANCH) or "").strip()[:128]
                if branch:
                    vehicle.branch_name = branch
                    branch_fix_count += 1
            if vehicle.purchase_invoice_date is None:
                invoice_date = _parse_turkish_date(source.get(COL_PURCHASE_INVOICE_DATE))
                if invoice_date:
                    vehicle.purchase_invoice_date = invoice_date
                    invoice_date_fix_count += 1

        self.stdout.write(f"Model/donanım ayrılacak araç: {model_fix_count}")
        self.stdout.write(f"Şube doldurulacak araç: {branch_fix_count}")
        self.stdout.write(f"Fatura tarihi doldurulacak araç: {invoice_date_fix_count}")
        if unmatched_plates:
            self.stdout.write(
                self.style.WARNING(
                    f"Excel'de eşleşmeyen {len(unmatched_plates)} plaka (şube/tarih atlandı), "
                    f"örnek: {unmatched_plates[:5]}"
                )
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: hiçbir şey kaydedilmedi."))
            return

        with transaction.atomic():
            Vehicle.objects.bulk_update(
                vehicles_needing_split, ["model", "package"], batch_size=200
            )
            Vehicle.objects.bulk_update(
                all_vehicles, ["branch_name", "purchase_invoice_date"], batch_size=200
            )

        self.stdout.write(self.style.SUCCESS("Geri doldurma tamamlandı."))
