"""Gerçekçi kiralama geçmişi + aktif/gelecek kiralama seed'i.

Şu ana kadar gider tarafı (kredi/nakit/sigorta/genel gider/operasyon)
gerçek veriyle dolu, ama gelir tarafı tamamen boş (``Rental``/
``RentalIncome`` = 0 satır) — bu yüzden ana sayfadaki Net Kazanç/Net Kar
her zaman 0/negatif. Bu komut, her aracın filoya giriş tarihinden bugüne
kadar gerçekçi bir doluluk deseniyle (boşluk + kiralama bloğu döngüsü)
Geçmiş/Aktif/Gelecek/İptal kiralamalar üretir, ve her Tamamlanmış/Aktif
blok için eşleşen bir ``RentalIncome`` satırı da oluşturur (``Rental``
tek başına gelir ekranlarını doldurmaz — ``RentalIncome`` tamamen ayrı,
bağımsız bir modeldir).

Fiyatlama: her aracın ``daily_rate``'i, o aracın GÜNCEL günlük maliyetinin
(``current_daily_cost``) sabit ×1,10 katı olarak belirlenir — bu, ana
sayfanın "Net Kazanç" hesabının (gelir − güncel_günlük_maliyet×kiralanan_gün)
kendi ölçüm mantığıyla birebir örtüştüğü için, toplamda gerçekten ~%10 kâr
marjı çıkmasını matematiksel olarak garanti eder (bkz. plan dosyası).
Günlük maliyeti hesaplanamayan (§1.5 — eksik veri) araçlar atlanır, uydurma
fiyat yazılmaz.

Kullanım::

    python manage.py seed_rental_history --dry-run
    python manage.py seed_rental_history
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone
from faker import Faker

from backend.apps.companies.models import Company
from backend.apps.customer_profiles.models import Driver, Gender
from backend.apps.rentals.choices import RentalStatus, ReturnStatus
from backend.apps.rentals.models import Rental
from backend.apps.vehicle_finance.models import RentalIncome
from backend.apps.vehicles.choices import VehicleStatus
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.rental_economics_service import (
    current_daily_cost,
)

MARGIN_MULTIPLIER = Decimal("1.10")
EXTRA_DRIVERS_PER_COMPANY = 40
MAX_HISTORICAL_BLOCKS_PER_VEHICLE = 60
CENTS = Decimal("0.01")

LATE_PENALTY_MULTIPLIER = Decimal("1.25")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def _aware(d: date, hour: int = 9) -> datetime:
    return timezone.make_aware(datetime.combine(d, time(hour, 0)))


class Command(BaseCommand):
    help = "Her araç için gerçekçi kiralama geçmişi + aktif/gelecek kiralama + gelir kaydı üretir."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run", action="store_true", help="Hiçbir şey kaydetmeden özet göster."
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Şirketin zaten kiralama kaydı olsa bile yine de ekle (varsayılan: atla).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        faker = Faker("tr_TR")
        today = date.today()

        total_summary: dict[str, dict[str, int]] = {}

        for company in Company.objects.all():
            if not force and Rental.objects.filter(vehicle__company=company).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"[{company.name}] zaten kiralama kaydı var, atlanıyor (--force ile üzerine ekleyin)."
                    )
                )
                continue

            self.stdout.write(f"=== {company.name} (id={company.pk}) ===")

            drivers = self._ensure_drivers(company, faker, dry_run)

            vehicles = list(Vehicle.objects.filter(company=company))
            priced_vehicles: list[tuple[Vehicle, Decimal]] = []
            skipped_no_cost = 0
            for vehicle in vehicles:
                daily = current_daily_cost(vehicle, today)
                if daily is None or vehicle.fleet_entry_date is None:
                    skipped_no_cost += 1
                    continue
                rate = _money(Decimal(str(daily)) * MARGIN_MULTIPLIER)
                priced_vehicles.append((vehicle, rate))

            if skipped_no_cost:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {skipped_no_cost} araç güncel günlük maliyet hesaplanamadığı için atlandı (§1.5)."
                    )
                )

            rentals: list[Rental] = []
            incomes: list[tuple[int, RentalIncome]] = []  # (index into rentals, income)
            vehicles_to_mark_rented: list[int] = []
            counts = {"completed": 0, "active": 0, "future": 0, "cancelled": 0}

            for vehicle, rate in priced_vehicles:
                # `priced_vehicles` yalnızca fleet_entry_date dolu araçları
                # içerir (yukarıdaki filtreleme döngüsüne bkz.).
                assert vehicle.fleet_entry_date is not None
                blocks = self._build_vehicle_timeline(vehicle.fleet_entry_date, today)
                km_cursor = max(0, vehicle.current_km - random.randint(2_000, 15_000))

                for block in blocks:
                    driver = random.choice(drivers)
                    duration_days = max((block["end"] - block["start"]).days, 1)

                    if block["kind"] == "completed":
                        outcome_roll = random.random()
                        started_at = _aware(block["start"])
                        original_ended_at = _aware(block["end"])
                        if outcome_roll < 0.075:
                            # ERKEN dönüş
                            early_days = random.randint(1, max(duration_days - 1, 1))
                            actual_return_at = original_ended_at - timedelta(days=early_days)
                            used_days = max(duration_days - early_days, 1)
                            price_difference = -_money(rate * early_days)
                            return_status = ReturnStatus.EARLY
                            base_amount = _money(rate * used_days)
                            late_fee = Decimal("0")
                            income_end = (actual_return_at.date())
                        elif outcome_roll < 0.15:
                            # GEÇ dönüş
                            late_days = random.randint(1, 5)
                            actual_return_at = original_ended_at + timedelta(days=late_days, hours=2)
                            price_difference = _money(rate * late_days * LATE_PENALTY_MULTIPLIER)
                            return_status = ReturnStatus.LATE
                            base_amount = _money(rate * duration_days)
                            late_fee = price_difference
                            income_end = actual_return_at.date()
                        else:
                            actual_return_at = original_ended_at + timedelta(minutes=random.randint(0, 45))
                            price_difference = Decimal("0")
                            return_status = ReturnStatus.ON_TIME
                            base_amount = _money(rate * duration_days)
                            late_fee = Decimal("0")
                            income_end = block["end"]

                        km_before = km_cursor
                        km_cursor = min(vehicle.current_km, km_cursor + duration_days * random.randint(60, 280))
                        rental = Rental(
                            driver=driver,
                            vehicle=vehicle,
                            status=RentalStatus.COMPLETED,
                            started_at=started_at,
                            ended_at=original_ended_at,
                            original_ended_at=original_ended_at,
                            actual_return_at=actual_return_at,
                            return_status=return_status,
                            price_difference=price_difference,
                            start_km=km_before,
                            end_km=km_cursor,
                            daily_rate=rate,
                            quoted_total=_money(rate * duration_days),
                        )
                        rentals.append(rental)
                        income = RentalIncome(
                            start_date=block["start"],
                            end_date=income_end,
                            base_amount=base_amount,
                            late_fee=late_fee,
                        )
                        incomes.append((len(rentals) - 1, income))
                        counts["completed"] += 1

                    elif block["kind"] == "active":
                        started_at = _aware(block["start"])
                        planned_end = _aware(block["end"])
                        elapsed_days = max((today - block["start"]).days, 1)
                        km_at_pickup = km_cursor
                        km_cursor = min(
                            vehicle.current_km, km_cursor + elapsed_days * random.randint(60, 280)
                        )
                        rental = Rental(
                            driver=driver,
                            vehicle=vehicle,
                            status=RentalStatus.ACTIVE,
                            started_at=started_at,
                            ended_at=planned_end,
                            original_ended_at=planned_end,
                            start_km=km_at_pickup,
                            daily_rate=rate,
                            quoted_total=_money(rate * duration_days),
                        )
                        rentals.append(rental)
                        income = RentalIncome(
                            start_date=block["start"],
                            end_date=today,
                            base_amount=_money(rate * elapsed_days),
                        )
                        incomes.append((len(rentals) - 1, income))
                        vehicles_to_mark_rented.append(vehicle.pk)
                        counts["active"] += 1

                    elif block["kind"] == "future":
                        started_at = _aware(block["start"])
                        planned_end = _aware(block["end"])
                        rentals.append(
                            Rental(
                                driver=driver,
                                vehicle=vehicle,
                                status=RentalStatus.ACTIVE,
                                started_at=started_at,
                                ended_at=planned_end,
                                original_ended_at=planned_end,
                                start_km=vehicle.current_km,
                                daily_rate=rate,
                                quoted_total=_money(rate * duration_days),
                            )
                        )
                        counts["future"] += 1

                    else:  # cancelled
                        started_at = _aware(block["start"])
                        planned_end = _aware(block["end"])
                        rentals.append(
                            Rental(
                                driver=driver,
                                vehicle=vehicle,
                                status=RentalStatus.CANCELLED,
                                started_at=started_at,
                                ended_at=planned_end,
                                original_ended_at=planned_end,
                                start_km=vehicle.current_km,
                                daily_rate=rate,
                                quoted_total=_money(rate * duration_days),
                            )
                        )
                        counts["cancelled"] += 1

            total_income = sum(
                (inc.base_amount + inc.late_fee for _, inc in incomes), Decimal("0")
            )
            self.stdout.write(
                f"  Kiralama: {counts['completed']} geçmiş, {counts['active']} aktif, "
                f"{counts['future']} gelecek, {counts['cancelled']} iptal — "
                f"toplam tahmini gelir ₺{total_income:,.2f}".replace(",", ".")
            )

            total_summary[company.name] = counts

            if dry_run:
                self.stdout.write(self.style.WARNING("  --dry-run: hiçbir şey kaydedilmedi."))
                continue

            with transaction.atomic():
                for rental in rentals:
                    rental.save()
                for rental_idx, income in incomes:
                    rental = rentals[rental_idx]
                    income.vehicle = rental.vehicle
                    income.rental = rental
                    income.save()
                if vehicles_to_mark_rented:
                    Vehicle.objects.filter(
                        pk__in=vehicles_to_mark_rented, status=VehicleStatus.AVAILABLE
                    ).update(status=VehicleStatus.RENTED)

            self.stdout.write(self.style.SUCCESS(f"  Kaydedildi: {len(rentals)} kiralama, {len(incomes)} gelir kaydı."))

        if dry_run:
            self.stdout.write(self.style.WARNING("Genel özet (--dry-run, hiçbir şey kaydedilmedi):"))
        else:
            self.stdout.write(self.style.SUCCESS("Tüm şirketler tamamlandı."))

    # ------------------------------------------------------------------
    def _ensure_drivers(self, company: Company, faker: Faker, dry_run: bool) -> list[Driver]:
        existing = list(Driver.objects.filter(company=company))
        if dry_run:
            self.stdout.write(
                f"  Mevcut sürücü: {len(existing)} (--dry-run: +{EXTRA_DRIVERS_PER_COMPANY} eklenecekti)."
            )
            return existing

        genders = [Gender.MALE, Gender.FEMALE, Gender.OTHER]
        cities = ("Ankara", "İstanbul", "İzmir", "Bursa", "Antalya", "Konya")
        license_classes = ("B", "B", "B", "BE", "C")
        new_drivers: list[Driver] = []
        for _ in range(EXTRA_DRIVERS_PER_COMPANY):
            gender = random.choice(genders)
            if gender == Gender.MALE:
                first = faker.first_name_male()
            elif gender == Gender.FEMALE:
                first = faker.first_name_female()
            else:
                first = faker.first_name()
            new_drivers.append(
                Driver(
                    company=company,
                    first_name=first,
                    last_name=faker.last_name(),
                    national_id=faker.unique.numerify("###########"),
                    gender=gender,
                    birth_date=faker.date_of_birth(minimum_age=22, maximum_age=65),
                    phone=faker.numerify("05## ### ## ##"),
                    email=faker.unique.email(),
                    license_number=faker.unique.bothify(text="??######"),
                    license_class=random.choice(license_classes),
                    city=random.choice(cities),
                    district=faker.city_suffix(),
                    address=faker.street_address()[:255],
                )
            )
        Driver.objects.bulk_create(new_drivers)
        self.stdout.write(f"  +{len(new_drivers)} yeni sürücü eklendi (toplam {len(existing) + len(new_drivers)}).")
        return existing + list(Driver.objects.filter(company=company).order_by("-id")[: len(new_drivers)])

    def _build_vehicle_timeline(self, entry: date, today: date) -> list[dict]:
        """Boşluk + kiralama bloğu döngüsüyle bir aracın tüm zaman çizelgesini üretir."""
        blocks: list[dict] = []
        cursor = entry
        safety_cutoff = today - timedelta(days=random.randint(0, 20))

        while cursor < safety_cutoff and len(blocks) < MAX_HISTORICAL_BLOCKS_PER_VEHICLE:
            gap = random.randint(3, 25)
            cursor = cursor + timedelta(days=gap)
            if cursor >= safety_cutoff:
                break
            duration = random.randint(2, 18)
            end = min(cursor + timedelta(days=duration), safety_cutoff)
            if (end - cursor).days >= 1:
                blocks.append({"kind": "completed", "start": cursor, "end": end})
            cursor = end

        # Kuyruk: araç şu an kirada mı (aktif), yoksa yakın zamanda mı döndü.
        if random.random() < 0.22:
            start = today - timedelta(days=random.randint(1, 14))
            duration = random.randint(3, 15)
            end = start + timedelta(days=duration)
            if start > entry:
                blocks.append({"kind": "active", "start": start, "end": end})
        elif random.random() < 0.6:
            duration = random.randint(2, 12)
            end = today - timedelta(days=random.randint(0, 6))
            start = end - timedelta(days=duration)
            if start > entry:
                blocks.append({"kind": "completed", "start": start, "end": end})

        if random.random() < 0.10:
            start = today + timedelta(days=random.randint(2, 20))
            duration = random.randint(2, 10)
            end = start + timedelta(days=duration)
            blocks.append({"kind": "future", "start": start, "end": end})

        if random.random() < 0.08:
            start = today + timedelta(days=random.randint(2, 20))
            duration = random.randint(2, 10)
            end = start + timedelta(days=duration)
            blocks.append({"kind": "cancelled", "start": start, "end": end})

        return blocks
