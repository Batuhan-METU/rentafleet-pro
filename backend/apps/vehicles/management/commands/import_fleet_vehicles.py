"""Gerçek filo envanteri Excel import — kullanıcının sağladığı toplu araç
listesinden (`Vehicle_duzeltilmis.xlsx` formatı) rastgele/katmanlı bir
örneklemi ``Vehicle`` tablosuna aktarır.

Neden katmanlı (stratified) örnekleme: kaynak dosyada 50+ farklı SIPP
segment kodu var; saf rastgele seçim en kalabalık 2-3 segmentte
yığılabilir. Bu komut SIPP koduna göre orantılı dağıtarak segment
çeşitliliğini korur (`--count` kadar araç, kaynak dağılımına orantılı).

Kaynak sütun → alan eşlemesi ve nedenleri kod içindeki `_row_to_fields`
fonksiyonunda belgelenmiştir. Eşlenemeyen/belirsiz alanlar (§1.5 ilkesiyle
tutarlı: tahmin üretilmez) boş/None bırakılır — örn. "Vites" boşsa ve
SIPP kodundan da çıkarılamıyorsa `transmission` boş kalır.

Kullanım::

    python manage.py import_fleet_vehicles ../Vehicle_duzeltilmis.xlsx \\
        --company-id 53 --count 100 --seed 42
"""

from __future__ import annotations

import random
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from backend.apps.companies.models import Company
from backend.apps.vehicles.choices import BodyType, FuelType, Transmission
from backend.apps.vehicles.models import Vehicle

# --- Kaynak sütun adları (Excel başlık satırı) --------------------------
COL_PLATE = "Plaka"
COL_CHASSIS = "Şasi Kodu"
COL_REGISTRATION = "Ruhsat Numarası"
COL_COLOR = "Araç Renk"
COL_SIPP = "Araç SIPP Kodu"
COL_BRAND = "Marka"
COL_MODEL = "Model - Donanım"
COL_YEAR = "Yıl"
COL_KM = "Kilometre"
COL_FUEL_TYPE = "Yakıt Cinsi"
COL_FUEL_CAPACITY = "Yakıt Kapasitesi"
COL_TRANSMISSION = "Vites"
COL_FLEET_ENTRY = "Filoya Giriş Tarihi"
COL_PURCHASE_PRICE = "Satın Alım Fiyatı"
COL_BRANCH = "Şube"
COL_PURCHASE_INVOICE_DATE = "Satın Alma (Fatura) Tarihi"

REQUIRED_COLUMNS = (
    COL_PLATE,
    COL_SIPP,
    COL_BRAND,
    COL_MODEL,
    COL_YEAR,
    COL_KM,
    COL_FUEL_TYPE,
    COL_FLEET_ENTRY,
    COL_PURCHASE_PRICE,
)

# Kaynaktaki dağınık/serbest metin marka adlarını temiz tekil isimlere indirger.
BRAND_NORMALIZATION: dict[str, str] = {
    "ALPİNE": "Alpine",
    "AUDI": "Audi",
    "BMW": "BMW",
    "BYD": "BYD",
    "CHRYSLER": "Chrysler",
    "CITROEN": "Citroen",
    "CUPRA": "Cupra",
    "DACIA": "Dacia",
    "FIAT": "Fiat",
    "FORD": "Ford",
    "FORD / OTOSAN": "Ford",
    "HYUNDAI": "Hyundai",
    "ISUZU": "Isuzu",
    "KIA": "Kia",
    "MAXUS": "Maxus",
    "MERCEDES": "Mercedes",
    "MG": "MG",
    "NISSAN": "Nissan",
    "OPEL": "Opel",
    "PEUGEOT": "Peugeot",
    "RENAULT": "Renault",
    "RENAULT (OYAK)": "Renault",
    "SEAT": "Seat",
    "SKODA": "Skoda",
    "SUZUKI": "Suzuki",
    "TOFAS-FIAT": "Fiat",
    "TOGG": "TOGG",
    "TOYOTA": "Toyota",
    "VOLKSWAGEN": "Volkswagen",
}

FUEL_TYPE_MAP: dict[str, str] = {
    "benzin": FuelType.GASOLINE,
    "dizel": FuelType.DIESEL,
    "hibrit": FuelType.HYBRID,
    "elektrikli": FuelType.ELECTRIC,
}

# Vites sütunu boşsa SIPP kodunun 3. harfinden çıkarılır (bkz. sipp_service._TRANSMISSION_TR).
SIPP_TRANSMISSION_MAP: dict[str, str] = {
    "M": Transmission.MANUAL,
    "N": Transmission.MANUAL,
    "C": Transmission.MANUAL,
    "A": Transmission.AUTOMATIC,
    "B": Transmission.AUTOMATIC,
    "D": Transmission.AUTOMATIC,
}

# SIPP kodunun 2. harfi — yalnızca net eşleşen kasa tipleri dolduruluyor;
# belirsiz olanlar (B/C/D/L/S/T/J/X/R) tahmin edilmeyip boş bırakılıyor.
SIPP_BODY_TYPE_MAP: dict[str, str] = {
    "F": BodyType.SUV,
    "W": BodyType.STATION_WAGON,
    "V": BodyType.MINIVAN,
    "P": BodyType.PICKUP,
    "Q": BodyType.PICKUP,
    "M": BodyType.VAN,
}

# SIPP kodunun 1. harfi — segment kategorisi (Türkçe, kullanıcıya görünür alan).
SIPP_CATEGORY_TR: dict[str, str] = {
    "M": "Mini",
    "E": "Ekonomik",
    "C": "Kompakt",
    "I": "Orta",
    "S": "Standart",
    "F": "Tam Boy",
    "P": "Premium",
    "L": "Lüks",
    "X": "Özel",
}

EXCLUDED_SIPP_CODES = {"TEST"}


def _parse_turkish_date(raw: object) -> date | None:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not raw:
        return None
    text = str(raw).strip().split(" ")[0]  # "13.04.2026 13:39" -> "13.04.2026"
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_turkish_decimal(raw: object) -> Decimal | None:
    """'1.000.000,00' (bin ayracı nokta, ondalık virgül) -> Decimal('1000000.00')."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))
    text = str(raw).strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _row_to_fields(row: dict[str, object], company: Company) -> dict[str, Any] | None:
    """Tek bir Excel satırını ``Vehicle.objects.create(**fields)`` sözlüğüne çevirir.

    Zorunlu bir alan eksik/anlamsızsa (plaka, SIPP, marka, model, yıl) satır
    atlanır — sessizce yarım veri üretmek yerine.
    """
    plate = str(row.get(COL_PLATE) or "").strip()
    sipp = str(row.get(COL_SIPP) or "").strip().upper()
    brand_raw = str(row.get(COL_BRAND) or "").strip()
    model_raw = str(row.get(COL_MODEL) or "").strip()
    year = row.get(COL_YEAR)
    if not (plate and sipp and brand_raw and model_raw and year):
        return None

    brand = BRAND_NORMALIZATION.get(brand_raw.upper(), brand_raw.title())
    # Kaynaktaki "Model - Donanım" sütunu ikisini birleşik tutar (ör.
    # "208 ACTIVE DYNAMIC 1.5 BLUEHDI 100 S&S"). İlk kelime model adı, kalanı
    # donanım paketi — ayrı alanlara böleriz (§ kullanıcı talebi).
    model_parts = model_raw.split(maxsplit=1)
    model = model_parts[0][:64]
    package = model_parts[1][:64] if len(model_parts) > 1 else ""

    fuel_type = FUEL_TYPE_MAP.get(str(row.get(COL_FUEL_TYPE) or "").strip().lower(), "")

    vites_raw = row.get(COL_TRANSMISSION)
    transmission: str
    if vites_raw == 1:
        transmission = Transmission.MANUAL
    elif vites_raw == 2:
        transmission = Transmission.AUTOMATIC
    else:
        transmission = SIPP_TRANSMISSION_MAP.get(sipp[2:3], "") if len(sipp) == 4 else ""

    body_type = SIPP_BODY_TYPE_MAP.get(sipp[1:2], "") if len(sipp) == 4 else ""
    segment = SIPP_CATEGORY_TR.get(sipp[0:1], "") if len(sipp) == 4 else ""

    current_km = row.get(COL_KM)
    try:
        current_km = int(current_km) if current_km is not None else 0  # type: ignore[call-overload]
    except (TypeError, ValueError):
        current_km = 0

    fuel_capacity = _parse_turkish_decimal(row.get(COL_FUEL_CAPACITY))

    return {
        "company": company,
        "plate_number": plate[:16],
        "brand": brand[:64],
        "model": model,
        "package": package,
        "sipp_code": sipp[:4],
        "production_year": int(year),  # type: ignore[call-overload]
        "current_km": max(current_km, 0),
        "fuel_type": fuel_type,
        "transmission": transmission,
        "body_type": body_type,
        "segment": segment,
        "color": str(row.get(COL_COLOR) or "").strip()[:32],
        "chassis_number": str(row.get(COL_CHASSIS) or "").strip()[:32],
        "registration_number": str(row.get(COL_REGISTRATION) or "").strip()[:32],
        "branch_name": str(row.get(COL_BRANCH) or "").strip()[:128],
        "fleet_entry_date": _parse_turkish_date(row.get(COL_FLEET_ENTRY)),
        "purchase_invoice_date": _parse_turkish_date(row.get(COL_PURCHASE_INVOICE_DATE)),
        "purchase_price": _parse_turkish_decimal(row.get(COL_PURCHASE_PRICE)),
        "fuel_tank_capacity_liters": fuel_capacity,
    }


def _stratified_sample(
    rows: list[dict[str, object]], count: int, rng: random.Random
) -> list[dict[str, object]]:
    """SIPP koduna göre orantılı, katmanlı rastgele örnekleme.

    Her segment grubundan, grubun kaynak dağılımdaki payına orantılı sayıda
    araç seçilir (en büyük kalan yöntemiyle tam ``count``'a tamamlanır);
    grup içindeki seçim rastgeledir. Böylece 100 araç, saf rastgele
    seçimin aksine tüm segmentlere yayılır.
    """
    groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        sipp = str(row.get(COL_SIPP) or "").strip().upper()
        if not sipp or sipp in EXCLUDED_SIPP_CODES:
            continue
        groups.setdefault(sipp, []).append(row)

    total = sum(len(g) for g in groups.values())
    if total == 0:
        return []
    count = min(count, total)

    quotas: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    for sipp, group in groups.items():
        exact = count * len(group) / total
        base = int(exact)
        quotas[sipp] = base
        remainders.append((exact - base, sipp))

    assigned = sum(quotas.values())
    remainders.sort(reverse=True)
    for _, sipp in remainders[: count - assigned]:
        quotas[sipp] += 1

    selected: list[dict[str, object]] = []
    for sipp, group in groups.items():
        quota = min(quotas.get(sipp, 0), len(group))
        selected.extend(rng.sample(group, quota))

    return selected


class Command(BaseCommand):
    help = (
        "Gerçek filo envanteri Excel'inden (Vehicle_duzeltilmis.xlsx formatı) "
        "SIPP segmentine göre katmanlı rastgele bir örneklemi bir şirkete aktarır."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("xlsx_path", type=str, help="Kaynak .xlsx dosya yolu.")
        parser.add_argument("--company-id", type=int, required=True, help="Hedef şirket ID.")
        parser.add_argument(
            "--count", type=int, default=100, help="Aktarılacak araç sayısı (varsayılan 100)."
        )
        parser.add_argument(
            "--seed", type=int, default=None, help="Rastgelelik için sabit tohum (tekrarlanabilirlik)."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Hiçbir şey kaydetmeden seçilecek araçların özetini göster.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError("openpyxl kurulu değil (pip install openpyxl).") from exc

        try:
            company = Company.objects.get(pk=options["company_id"])
        except Company.DoesNotExist as exc:
            raise CommandError(f"Şirket bulunamadı: id={options['company_id']}") from exc

        xlsx_path: str = options["xlsx_path"]
        try:
            workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
        except (OSError, KeyError) as exc:
            raise CommandError(f"Dosya okunamadı: {xlsx_path} ({exc})") from exc

        sheet = workbook[workbook.sheetnames[0]]
        rows_iter = sheet.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
        missing = [c for c in REQUIRED_COLUMNS if c not in header]
        if missing:
            raise CommandError(f"Eksik sütun(lar): {missing}")

        raw_rows = [dict(zip(header, row)) for row in rows_iter]
        self.stdout.write(f"Kaynakta {len(raw_rows)} satır bulundu.")

        rng = random.Random(options["seed"])
        sample = _stratified_sample(raw_rows, options["count"], rng)
        rng.shuffle(sample)  # katman sırasına göre değil, karışık listelensin

        existing_plates = set(
            Vehicle.objects.filter(company=company).values_list("plate_number", flat=True)
        )

        to_create: list[Vehicle] = []
        skipped_duplicate = 0
        skipped_invalid = 0
        segment_counts: dict[str, int] = {}

        for row in sample:
            fields = _row_to_fields(row, company)
            if fields is None:
                skipped_invalid += 1
                continue
            if fields["plate_number"] in existing_plates:
                skipped_duplicate += 1
                continue
            existing_plates.add(fields["plate_number"])
            segment_counts[fields["sipp_code"]] = segment_counts.get(fields["sipp_code"], 0) + 1
            to_create.append(Vehicle(**fields))

        self.stdout.write(
            f"{len(to_create)} araç aktarıma hazır "
            f"({skipped_invalid} geçersiz satır, {skipped_duplicate} zaten mevcut plaka atlandı)."
        )
        self.stdout.write(f"{len(segment_counts)} farklı SIPP segmenti temsil ediliyor.")

        if options["dry_run"]:
            for vehicle in to_create[:15]:
                self.stdout.write(
                    f"  - {vehicle.plate_number} | {vehicle.brand} {vehicle.model} "
                    f"| {vehicle.sipp_code} | {vehicle.production_year} | {vehicle.current_km} km"
                )
            if len(to_create) > 15:
                self.stdout.write(f"  ... ve {len(to_create) - 15} tane daha.")
            self.stdout.write(self.style.WARNING("--dry-run: hiçbir şey kaydedilmedi."))
            return

        with transaction.atomic():
            Vehicle.objects.bulk_create(to_create)

        self.stdout.write(self.style.SUCCESS(f"{len(to_create)} araç '{company.name}' şirketine aktarıldı."))
