"""Sürücü kayıt sinyalleri — risk skorunun anında hesaplanması."""

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from backend.application.driver.evaluate_driver import DriverEvaluationService
from backend.apps.customer_profiles.models import Driver


def _evaluate_driver_risk_on_commit(driver_id: int) -> None:
    try:
        driver = Driver.objects.get(pk=driver_id)
    except Driver.DoesNotExist:
        return

    if driver.current_risk_score is not None:
        return

    DriverEvaluationService().evaluate(driver)


@receiver(post_save, sender=Driver)
def evaluate_driver_risk_after_create(sender, instance: Driver, created: bool, **kwargs) -> None:
    if not created:
        return
    transaction.on_commit(lambda: _evaluate_driver_risk_on_commit(instance.pk))
