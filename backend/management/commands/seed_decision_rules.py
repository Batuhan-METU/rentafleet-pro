"""Varsayılan karar kurallarını veritabanına yazar."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from backend.domain.risk.rules import build_default_risk_rules
from backend.apps.risk_checks.models import (
    RuleDefinition,
    RuleEngineType,
    RuleSet,
)
from backend.apps.companies.models import Company


class Command(BaseCommand):
    help = "Şirketler için varsayılan risk kural setlerini oluşturur."

    def handle(self, *args, **options):
        companies = Company.objects.all()
        if not companies.exists():
            self.stdout.write(self.style.WARNING("Şirket bulunamadı — önce seed_data çalıştırın."))
            return

        created_sets = 0
        created_rules = 0

        for company in companies:
            rule_set, was_created = RuleSet.objects.get_or_create(
                company=company,
                engine=RuleEngineType.RISK,
                version="1.0.0",
                defaults={
                    "name": "Varsayılan Risk Kuralları",
                    "is_active": True,
                },
            )
            if was_created:
                created_sets += 1

            existing_codes = set(
                rule_set.rules.values_list("code", flat=True),
            )
            for rule in build_default_risk_rules():
                if rule.code in existing_codes:
                    continue
                RuleDefinition.objects.create(
                    rule_set=rule_set,
                    code=rule.code,
                    priority=rule.priority,
                    effect=rule.effect.value,
                    points=rule.points,
                    message=rule.message,
                    condition={"type": "code", "code": rule.code},
                )
                created_rules += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Tamamlandı: {created_sets} yeni kural seti, {created_rules} yeni kural.",
            ),
        )