"""Enuygun API üzerinden filo piyasa fiyatlarını çekip CompetitorPrice tablosunu günceller.

Kullanım::

    python manage.py fetch_competitor_prices
    python manage.py fetch_competitor_prices --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandParser

from api.services.comparable_vehicle_service import sync_fleet_market_prices


class Command(BaseCommand):
    help = "Tüm filo için Enuygun piyasa fiyatlarını çeker ve CompetitorPrice günceller."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Veritabanına yazmadan yalnızca bilgi ver (senkron atlanır).",
        )

    def handle(self, *args, **options) -> None:
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "dry-run: gerçek senkron için bayrağı kaldırın."
                )
            )
            return

        self.stdout.write("Filo piyasa senkronu başlıyor (Enuygun API, Ankara)...")
        result = sync_fleet_market_prices()
        self.stdout.write(
            self.style.SUCCESS(
                f"Tamamlandı: {result['arac_sayisi']} araç, "
                f"{result['kayit_sayisi']} fiyat kaydı "
                f"({result['cekilen_rezervasyon']}/{result['toplam_rezervasyon']} rezervasyon)."
            )
        )
        for err in result.get("hatalar", []):
            self.stdout.write(self.style.WARNING(f"  · {err}"))
