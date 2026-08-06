"""Kredi/tahsis verisini siler ve GERÇEK kaynak eşleştirmesine göre yeniden
oluşturur — "hangi araç hangi krediden alındı" artık benim uydurduğum bir
tarih-yakınlığı sezgisi DEĞİL, ``datas/Kredi_Arac_Eslestirme.xlsx``'teki
gerçek (ZiraatFilo referans projesinden) kredi-araç eşleştirmesi.

**Neden önceki sürüm (tarih-kümeleme) yanlıştı:** İlk sürüm, LOAN/MIXED
araçları şirket başına sabit sayıda gruba bölüyordu; bu bazı gruplarda
araçların ``fleet_entry_date``'lerinin 5 yıla yayılmasına yol açtı (bir
kredi 2020-2025 arası filoya giren araçları tek krediye topladı), bu da
vadesi dolmuş kredilerde bazı araçların (ör. 34DCV512) kendi payının
30+ katı "tahakkuk" göstermesine sebep oldu — çünkü erken giren araç,
diğerleri henüz filoya girmeden geçen yıllarda havuzda YALNIZDI.

**Bu sürüm ne yapıyor:**
1. ``Kredi_Arac_Eslestirme.xlsx`` (Kredi No, Şasi Kodu, Plaka) plaka ile
   eşleştirilip, GERÇEK kaynak projede hangi aracın hangi krediye
   bağlı olduğu birebir okunuyor — kümeleme/tahmin YOK.
2. ``Krediler.xlsx``'ten o kredinin GERÇEK banka adı, aylık faiz oranı,
   vadesi ve başlangıç tarihi alınıyor (ZiraatFilo'nun kendi verisi,
   sentetik değil).
3. **``principal_amount`` GERÇEK ZiraatFilo tutarı (₺55M-1 milyar TL)
   DEĞİL** — sadece BİZİM sistemimizdeki, o krediye gerçekten bağlı
   araçların ``financed_amount`` toplamı kullanılır. Gerçek tutarı
   olduğu gibi kullansaydık (bizim sadece 1-2 aracımız o krediye
   bağlıyken), taksit tutarı ZiraatFilo'nun tüm filosuna göre
   hesaplanır ama sadece bizim 1-2 aracımıza dağıtılır — bu, düzelttiğimiz
   bug'dan daha kötü bir çarpıtmaya yol açardı. Gerçek olan SADECE
   "hangi araçlar aynı kredide" ve "bu kredinin şartları (banka/oran/
   vade/başlangıç)" — tutar bizim küçük ölçeğimize göre yeniden hesaplanır.
4. Bir araç birden fazla gerçek krediye bağlıysa (kaynak veride bir plaka
   birden fazla Kredi No satırında geçiyorsa), bizim sistemimizde de
   AYNI ŞEKİLDE birden fazla ``LoanVehicleAllocation`` oluşturulur —
   ``accrued_credit_cost_for_vehicle`` zaten tüm bağlı kredileri toplar.
5. Kaynak eşleştirmede bulunamayan LOAN/MIXED araçlar (plaka kaynak
   dosyada yoksa) için, BAŞKA araçlarla hangi krediyi paylaştığı TAHMİN
   EDİLMEZ — her biri için tek başına, yeni bir kredi açılır. Tutar ve
   başlangıç tarihi aracın KENDİ bilinen gerçek verisidir (kredi payı,
   fleet_entry_date); sadece banka adı/vade, gerçek bir referansı
   olmadığı için makul bir havuzdan seçilir.

Kullanım::

    python manage.py reseed_vehicle_loans
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from itertools import cycle
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from backend.apps.vehicle_finance.choices import FinancingType
from backend.apps.vehicle_finance.models import (
    Loan,
    LoanInstallment,
    LoanVehicleAllocation,
    VehicleFinancialProfile,
)
from backend.infrastructure.services.cost_calculation.credit_interest_service import (
    generate_amortization_schedule,
    validate_loan_distribution,
)

MATCHING_FILE = "../datas/Kredi_Arac_Eslestirme.xlsx"
LOANS_FILE = "../datas/Krediler.xlsx"

BANK_DISPLAY_NAMES = {
    "AKBANK": "Akbank",
    "ANADOLUBANK": "Anadolubank",
    "BURGAN": "Burgan Bank",
    "DENIZBANK": "Denizbank",
    "ISBANK": "İş Bankası",
    "MERCEDES": "Mercedes-Benz Finansman",
    "VAKIFBANK": "Vakıfbank",
    "VAKIFKATILIM": "Vakıf Katılım",
    "VDF": "VDF Faktoring",
    "YKB": "Yapı Kredi",
    "ZIRAAT": "Ziraat Bankası",
}


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
    help = "Kredi/tahsis verisini siler, gerçek Kredi_Arac_Eslestirme.xlsx eşleştirmesine göre yeniden oluşturur."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run", action="store_true", help="Hiçbir şey kaydetmeden özet göster."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            import openpyxl
        except ImportError as exc:
            raise CommandError("openpyxl kurulu değil.") from exc

        # --- 1) Gerçek kredi parametreleri (Krediler.xlsx) ------------------
        try:
            wb_loans = openpyxl.load_workbook(LOANS_FILE, read_only=True, data_only=True)
        except (OSError, KeyError) as exc:
            raise CommandError(f"Dosya okunamadı: {LOANS_FILE} ({exc})") from exc
        ws_loans = wb_loans.active
        loan_rows = list(ws_loans.iter_rows(values_only=True))
        loan_header = [str(h).strip() if h is not None else "" for h in loan_rows[0]]
        li = {h: i for i, h in enumerate(loan_header)}
        real_loans: dict[str, dict[str, Any]] = {}
        for row in loan_rows[1:]:
            loan_no = str(row[li["Kredi No"]] or "").strip()
            if not loan_no:
                continue
            real_loans[loan_no] = {
                "bank_raw": str(row[li["Banka"]] or "").strip(),
                "monthly_rate": Decimal(str(row[li["Faiz (Aylık %)"]] or 0)) / Decimal(100),
                "term_months": int(row[li["Vade (Ay)"]] or 0),
                "start_date": _parse_turkish_date(row[li["Başlangıç Tarihi"]]),
                "end_date": _parse_turkish_date(row[li["Bitiş Tarihi"]]),
            }

        # --- 2) Gerçek araç-kredi eşleştirmesi (Kredi_Arac_Eslestirme.xlsx) --
        try:
            wb_match = openpyxl.load_workbook(MATCHING_FILE, read_only=True, data_only=True)
        except (OSError, KeyError) as exc:
            raise CommandError(f"Dosya okunamadı: {MATCHING_FILE} ({exc})") from exc
        ws_match = wb_match.active
        match_rows = list(ws_match.iter_rows(values_only=True))
        match_header = [str(h).strip() if h is not None else "" for h in match_rows[0]]
        mi = {h: i for i, h in enumerate(match_header)}
        plate_to_loan_nos: dict[str, list[str]] = {}
        for row in match_rows[1:]:
            plate = str(row[mi["Plaka"]] or "").strip()
            loan_no = str(row[mi["Kredi No"]] or "").strip()
            if not plate or not loan_no:
                continue
            plate_to_loan_nos.setdefault(plate, []).append(loan_no)

        # --- 3) Bizim LOAN/MIXED araçlarımızı gerçek kredi no'larına göre grupla --
        profiles = VehicleFinancialProfile.objects.filter(
            financing_type__in=[FinancingType.LOAN, FinancingType.MIXED]
        ).select_related("vehicle")

        by_loan_no: dict[str, list[dict[str, Any]]] = {}
        unmatched: list[dict[str, Any]] = []
        for profile in profiles:
            vehicle = profile.vehicle
            if vehicle.purchase_price is None:
                continue
            cash = profile.cash_financed_amount or Decimal("0")
            financed_amount = Decimal(vehicle.purchase_price) - Decimal(cash)
            if financed_amount <= 0:
                continue
            loan_nos = plate_to_loan_nos.get(vehicle.plate_number)
            # Sadece parametreleri (Krediler.xlsx'te) tanınan gerçek krediler
            # sayılır — aksi halde "N krediye bölündü" sanılıp payı gereksiz
            # küçültülmüş olur.
            valid_loan_nos = [ln for ln in (loan_nos or []) if ln in real_loans]
            if not valid_loan_nos:
                unmatched.append({"vehicle": vehicle, "financed_amount": financed_amount})
                continue
            # Araç BİRDEN FAZLA gerçek krediye bağlıysa, kaynak veri hangi
            # krediden ne kadar geldiğini AYRI AYRI vermiyor (Kredi_Arac_
            # Eslestirme.xlsx'teki tutar sütunu her satırda kredinin KENDİ
            # toplamı, araca özel pay değil — daha önce doğrulandı). Gerçek
            # bir oran kaynağı olmadığından araçların TOPLAM kredi payı
            # eşit olarak bölünür — bu sayede bir araç 2 krediye bağlı
            # olduğunda toplamı yine kendi satın alım fiyatını AŞMAZ
            # (double-counting yapılmaz), ama araç yine her iki kredinin
            # tahsis listesinde görünür ve her ikisinden eş zamanlı maliyet
            # tahakkuk eder (bkz. accrued_credit_cost_for_vehicle — tüm
            # bağlı kredileri zaten topluyor).
            split_amount = (financed_amount / len(valid_loan_nos)).quantize(Decimal("0.01"))
            for loan_no in valid_loan_nos:
                by_loan_no.setdefault(loan_no, []).append(
                    {"vehicle": vehicle, "financed_amount": split_amount}
                )

        loans_plan: list[dict[str, Any]] = []
        for loan_no, allocations in by_loan_no.items():
            real = real_loans[loan_no]
            if real["start_date"] is None or real["term_months"] <= 0:
                continue
            company_ids = {a["vehicle"].company_id for a in allocations}
            if len(company_ids) > 1:
                # Aynı gerçek kredi bizim ayrı şirketlerimizdeki araçlara
                # denk geldiyse (kaynak evren 1595 araç, bizimkiler 3 ayrı
                # kiracıya dağıtılmış) — şirket başına AYRI kredi açılır,
                # kredi bir kiracıdan diğerine sızmaz.
                by_company: dict[int, list[dict[str, Any]]] = {}
                for a in allocations:
                    by_company.setdefault(a["vehicle"].company_id, []).append(a)
                groups = list(by_company.items())
            else:
                groups = [(next(iter(company_ids)), allocations)]

            for company_id, group in groups:
                loans_plan.append(
                    {
                        "loan_no": loan_no,
                        "company_id": company_id,
                        "lender_name": BANK_DISPLAY_NAMES.get(real["bank_raw"], real["bank_raw"].title()),
                        "monthly_rate": real["monthly_rate"],
                        "term_months": real["term_months"],
                        "start_date": real["start_date"],
                        "end_date": real["end_date"],
                        "principal_amount": sum(
                            (a["financed_amount"] for a in group), Decimal("0")
                        ),
                        "allocations": group,
                    }
                )

        # --- 4) Gerçek eşleştirmede bulunamayan araçlar — TAHMİN/kümeleme
        # YAPILMAZ (diğer araçlarla hangi krediyi paylaştığını uydurmuyoruz).
        # Bunun yerine her biri için TEK BAŞINA, yeni bir kredi açılır —
        # tutar aracın kendi (bilinen, gerçek) kredi payı, başlangıç tarihi
        # aracın kendi (bilinen, gerçek) filoya giriş tarihi; sadece banka
        # adı ve vade gerçek bir referansı olmayan yeni bir kredi olduğu
        # için makul bir havuzdan seçilir. Hiçbir araç BAŞKA bir aracın
        # kredisine eklenmez — "kiminle aynı kredide" sorusu hiç sorulmaz.
        fallback_banks = cycle(BANK_DISPLAY_NAMES.values())
        fallback_terms = cycle([36, 24, 40])
        for entry in unmatched:
            vehicle = entry["vehicle"]
            if vehicle.fleet_entry_date is None:
                continue
            loans_plan.append(
                {
                    "loan_no": f"YENİ-{vehicle.plate_number}",
                    "company_id": vehicle.company_id,
                    "lender_name": next(fallback_banks),
                    "monthly_rate": Decimal("0.03"),
                    "term_months": next(fallback_terms),
                    "start_date": vehicle.fleet_entry_date,
                    "end_date": None,
                    "principal_amount": entry["financed_amount"],
                    "allocations": [entry],
                }
            )

        self.stdout.write(f"Toplam kredi kümesi: {len(loans_plan)}")
        self.stdout.write(
            f"  ({len(loans_plan) - len(unmatched)} gerçek eşleştirmeden, "
            f"{len(unmatched)} tek-araçlık yeni kredi olarak açıldı)"
        )
        for plan in loans_plan:
            self.stdout.write(
                f"  - {plan['lender_name']} ({plan['loan_no']}, şirket {plan['company_id']}): "
                f"{plan['principal_amount']:,.2f} TL (bizim payımız), {len(plan['allocations'])} araç, "
                f"%{plan['monthly_rate']*100:.2f} aylık, {plan['term_months']} ay, başlangıç {plan['start_date']}"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: hiçbir şey kaydedilmedi."))
            return

        with transaction.atomic():
            deleted_installments = LoanInstallment.objects.all().delete()
            deleted_allocations = LoanVehicleAllocation.objects.all().delete()
            deleted_loans = Loan.objects.all().delete()
            self.stdout.write(
                f"Silindi: {deleted_loans[0]} kredi, {deleted_allocations[0]} tahsis, "
                f"{deleted_installments[0]} taksit."
            )

            created_loans: list[Loan] = []
            for plan in loans_plan:
                loan = Loan.objects.create(
                    company_id=plan["company_id"],
                    loan_no=plan["loan_no"],
                    lender_name=plan["lender_name"],
                    principal_amount=plan["principal_amount"],
                    monthly_interest_rate=plan["monthly_rate"],
                    term_months=plan["term_months"],
                    start_date=plan["start_date"],
                    end_date=plan.get("end_date"),
                )
                LoanVehicleAllocation.objects.bulk_create(
                    LoanVehicleAllocation(
                        loan=loan,
                        vehicle=entry["vehicle"],
                        financed_amount=entry["financed_amount"],
                    )
                    for entry in plan["allocations"]
                )
                generate_amortization_schedule(loan)
                created_loans.append(loan)

        self.stdout.write(self.style.SUCCESS(f"{len(created_loans)} kredi (gerçek eşleştirmeyle) oluşturuldu."))

        invalid = 0
        for loan in created_loans:
            result = validate_loan_distribution(loan)
            if not result["is_valid"]:
                invalid += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ! {loan.lender_name}: dağıtım tutmuyor — fark {result.get('difference')}"
                    )
                )
        if invalid == 0:
            self.stdout.write(self.style.SUCCESS("Tüm kredilerin taksit dağılımı doğrulandı (fark ~0)."))
