"""Idempotency-Key desteği — tekrarlanan POST isteklerinin aynı kaynağı
iki kez oluşturmasını önleyen küçük, tek-amaçlı altyapı app'i."""

from django.apps import AppConfig


class IdempotencyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.idempotency"
    label = "idempotency"
    verbose_name = "Idempotency"
