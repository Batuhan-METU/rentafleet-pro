"""Enuygun API üzerinden filo piyasa fiyatlarını çekip CompetitorPrice tablosunu günceller.

Kullanım::

    python manage.py fetch_competitor_prices
    python manage.py fetch_competitor_prices --dry-run
    python manage.py fetch_competitor_prices --company-id 1
    python manage.py fetch_competitor_prices --company-id 1 --start-date 2026-08-01 --end-date 2026-08-05
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError, CommandParser

from backend.infrastructure.services.market.comparable_vehicle_service import sync_fleet_market_prices
from backend.infrastructure.services.common.date_helper import parse_date_param, rental_window, rental_window_from_dates


class Command(BaseCommand):
    help = "Enuygun piyasa fiyatlarını çeker ve CompetitorPrice tablosunu günceller."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Veritabanına yazmadan yalnızca bilgi ver (senkron atlanır).",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Kiralama başlangıç tarihi (YYYY-MM-DD). --end-date ile birlikte kullanın.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="Kiralama bitiş tarihi (YYYY-MM-DD). --start-date ile birlikte kullanın.",
        )
        parser.add_argument(
            "--company-id",
            type=int,
            required=True,
            help="Hangi kiracı (şirket) filosu için CompetitorPrice üretileceği.",
        )

    def handle(self, *args, **options) -> None:
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("dry-run: gerçek senkron için bayrağı kaldırın.")
            )
            return

        start_raw = options.get("start_date")
        end_raw = options.get("end_date")
        if bool(start_raw) ^ bool(end_raw):
            raise CommandError("--start-date ve --end-date birlikte verilmelidir.")

        if start_raw and end_raw:
            try:
                window = rental_window_from_dates(
                    parse_date_param(start_raw, field_name="start-date"),
                    parse_date_param(end_raw, field_name="end-date"),
                )
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
            label = f"{window.pickup_date_iso} → {window.dropoff_date_iso}"
        else:
            window = rental_window()
            label = f"varsayılan ({window.pickup_date_iso} → {window.dropoff_date_iso})"

        company_id: int = options["company_id"]

        self.stdout.write(f"Enuygun snapshot senkronu başlıyor — {label} (Ankara, kiracı #{company_id})...")
        result = sync_fleet_market_prices(force=True, window=window, company_id=company_id)
        onbellek = result.get("onbellek") or {}
        kaynak = "önbellek" if onbellek.get("from_cache") else "Enuygun API"
        self.stdout.write(
            self.style.SUCCESS(
                f"Tamamlandı ({kaynak}): {result['arac_sayisi']} araç, "
                f"{result['kayit_sayisi']} fiyat kaydı "
                f"({result['cekilen_rezervasyon']} rezervasyon)."
            )
        )
        for err in result.get("hatalar", []):
            self.stdout.write(self.style.WARNING(f"  · {err}"))