"""Kiralama oluşturma — hem ``RentalListCreateView`` hem AI asistanının
``create_rental`` tool'u tarafından çağrılan TEK iş mantığı kaynağı.

Bu fonksiyon HTTP'den bağımsızdır (ne ``Request`` ne ``Response`` bilir) —
hatalar ``rest_framework.exceptions.ValidationError`` fırlatarak bildirilir,
her iki çağıran da (DRF view, AI tool) bunu kendi yoluyla (otomatik 400
yanıtı / onay-öncesi hata mesajı) yakalar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from django.db import transaction
from django.db.models import Manager, QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from backend.application.customer.rental_stats import sync_rental_history_stats
from backend.application.rental.rental_guard import enforce_risk_and_eligibility
from backend.apps.companies.models import Company, CustomUser
from backend.apps.customer_profiles.models import Driver
from backend.apps.rentals.models import Rental, RentalStatus
from backend.apps.vehicles.models import Vehicle, VehicleStatus
from backend.common.audit import log_change


def datetime_at(d: date, t: time) -> datetime:
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(d, t), tz)


@dataclass
class RentalCreateInput:
    driver: Driver
    vehicle: Vehicle
    pickup_date: date
    dropoff_date: date
    pickup_time: time = time(10, 0)
    dropoff_time: time = time(10, 0)
    daily_rate: Decimal | None = None
    deposit_amount: Decimal | None = None


def _has_conflict(
    qs: QuerySet[Rental] | Manager[Rental], *, started_at: datetime, ended_at: datetime
) -> bool:
    return qs.filter(
        status=RentalStatus.ACTIVE, started_at__lt=ended_at, ended_at__gt=started_at
    ).exists()


def create_rental(*, company: Company, data: RentalCreateInput, created_by: CustomUser) -> Rental:
    driver = data.driver
    vehicle = data.vehicle
    started_at = datetime_at(data.pickup_date, data.pickup_time)
    ended_at = datetime_at(data.dropoff_date, data.dropoff_time)
    now = timezone.now()
    is_future = started_at > now

    total_days = max((data.dropoff_date - data.pickup_date).days, 1)
    quoted_total = data.daily_rate * total_days if data.daily_rate is not None else None

    if _has_conflict(driver.rentals, started_at=started_at, ended_at=ended_at):
        raise ValidationError({"error": "Sürücünün bu tarihlerde çakışan bir kiralaması var."})
    if _has_conflict(vehicle.rentals, started_at=started_at, ended_at=ended_at):
        raise ValidationError({"error": "Aracın bu tarihlerde çakışan bir kiralaması var."})
    if not is_future and vehicle.status != VehicleStatus.AVAILABLE:
        raise ValidationError({"error": "Seçilen araç müsait değil."})

    # Risk + araç uygunluk kapısı: taze bir risk değerlendirmesi çalıştırır,
    # RentalDecisionLog'a yazar. Bilerek DIŞARIDA (aşağıdaki atomic bloğun
    # dışında) çalıştırılır — reddedilen bir denemenin denetim kaydı, alttaki
    # blok hiç çalışmasa bile kalıcı olsun diye (bkz. rental_guard.py).
    application = enforce_risk_and_eligibility(
        company=company,
        driver=driver,
        vehicle=vehicle,
        created_by=created_by,
        requested_pickup_at=started_at,
        requested_return_at=ended_at,
    )

    with transaction.atomic():
        # Yarış durumu koruması: yukarıdaki kontroller kilitsizdi (hızlı yol);
        # burada satırlar kilitlenip aynı kontrol TEKRAR yapılır (bkz.
        # RentalCancelView/return_processing'deki aynı desen).
        locked_vehicle = Vehicle.objects.select_for_update().get(pk=vehicle.pk)
        locked_driver = Driver.objects.select_for_update().get(pk=driver.pk)

        if _has_conflict(locked_driver.rentals, started_at=started_at, ended_at=ended_at):
            raise ValidationError({"error": "Sürücünün bu tarihlerde çakışan bir kiralaması var."})
        if _has_conflict(locked_vehicle.rentals, started_at=started_at, ended_at=ended_at):
            raise ValidationError({"error": "Aracın bu tarihlerde çakışan bir kiralaması var."})
        if not is_future and locked_vehicle.status != VehicleStatus.AVAILABLE:
            raise ValidationError({"error": "Seçilen araç müsait değil."})

        rental = Rental.objects.create(
            driver=locked_driver,
            vehicle=locked_vehicle,
            status=RentalStatus.ACTIVE,
            started_at=started_at,
            ended_at=ended_at,
            original_ended_at=ended_at,
            start_km=locked_vehicle.current_km,
            quoted_total=quoted_total,
            daily_rate=data.daily_rate,
            deposit_amount=data.deposit_amount,
            application=application,
        )

        if not is_future:
            locked_vehicle.status = VehicleStatus.RENTED
            locked_vehicle.save(update_fields=["status"])

        sync_rental_history_stats(locked_driver)
        log_change(
            user=created_by,
            obj=rental,
            message=f"Kiralama oluşturuldu: {locked_driver} → {locked_vehicle.plate_number}.",
            created=True,
        )

    return rental
