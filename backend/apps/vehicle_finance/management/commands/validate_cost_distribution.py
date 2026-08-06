"""§10 madde 5 doğrulaması — her kredi için dağıtılan toplam == taksit toplamı mı.

Kullanım::

    python manage.py validate_cost_distribution
    python manage.py validate_cost_distribution --company-id 1
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from backend.apps.vehicle_finance.models import Loan
from backend.infrastructure.services.cost_calculation.credit_interest_service import (
    validate_loan_distribution,
)


class Command(BaseCommand):
    help = "Her kredi için dağıtılan toplam == taksit toplamı doğrulamasını çalıştırır (§10 madde 5)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--company-id", type=int, default=None, help="Sadece bu şirketin kredileri."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        loans = Loan.objects.all()
        if options["company_id"] is not None:
            loans = loans.filter(company_id=options["company_id"])

        total = 0
        failed = 0
        for loan in loans.order_by("company_id", "id"):
            total += 1
            result = validate_loan_distribution(loan)
            label = self.style.SUCCESS("OK") if result["is_valid"] else self.style.ERROR("HATA")
            self.stdout.write(
                f"[{label}] Loan #{loan.id} (şirket {loan.company_id}) — "
                f"dağıtılan={result.get('distributed_total')} "
                f"taksit={result.get('installment_total')} "
                f"fark={result.get('difference')} "
                f"{result.get('message', '')}"
            )
            if not result["is_valid"]:
                failed += 1

        if total == 0:
            self.stdout.write(self.style.WARNING("Hiç kredi bulunamadı."))
        elif failed:
            self.stdout.write(self.style.ERROR(f"{failed}/{total} kredi doğrulaması BAŞARISIZ."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Tüm {total} kredi doğrulaması geçti."))
