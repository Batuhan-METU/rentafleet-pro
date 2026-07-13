"""Skoru hesaplanmamış mevcut sürücüler için risk değerlendirmesi çalıştırır."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from backend.application.customer.snapshots import ensure_customer_profiles
from backend.application.driver.evaluate_driver import DriverEvaluationService
from backend.apps.customer_profiles.models import Driver


class Command(BaseCommand):
    help = "Mevcut tüm sürücüler için risk skorunu hesaplar ve veritabanına yazar."

    def handle(self, *args, **options) -> None:
        pending = Driver.objects.filter(
            Q(current_risk_score__isnull=True) | Q(risk_level="")
        ).order_by("id")

        total = pending.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Tüm sürücülerin risk skoru mevcut."))
            return

        service = DriverEvaluationService()
        updated = 0
        for driver in pending.iterator():
            ensure_customer_profiles(driver)
            service.evaluate(driver)
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated}/{total} sürücü için risk skoru hesaplandı."))
