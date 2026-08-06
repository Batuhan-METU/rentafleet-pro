"""Araç teslim alma — erken/geç/zamanında sınıflandırma ve fiyat farkı.

Tek çekirdek hesaplama fonksiyonu (``compute_return_settlement``) hem önizleme
hem kalıcı kayıt (commit) için kullanılır; böylece önizlemede gösterilen tutar
ile gerçekte tahsil/iade edilen tutar arasında asla sapma olmaz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from backend.application.customer.rental_stats import sync_rental_history_stats
from backend.application.driver.evaluate_driver import DriverEvaluationService
from backend.apps.rentals.models import Rental, RentalStatus, ReturnStatus
from backend.apps.vehicle_finance.models import RentalIncome
from backend.apps.vehicles.models import VehicleStatus
from backend.infrastructure.services.cost_calculation.rental_economics_service import (
    current_daily_cost,
)
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES

# Rötar toleransı: bu süreye kadarki gecikmeler ücretsizdir (ON_TIME sayılır).
LATE_GRACE_HOURS = 2
# Tolerans sonrası her ek gün için uygulanan aşım cezası katsayısı.
LATE_PENALTY_MULTIPLIER = Decimal("1.25")


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ReturnSettlement:
    return_status: str
    unused_days: int
    overage_hours: float
    daily_rate: Decimal
    price_difference: Decimal
    message: str


def _daily_rate(rental: Rental) -> Decimal:
    if rental.daily_rate:
        return Decimal(rental.daily_rate)

    # `ended_at` modelde null=True (bkz. Rental) ama bu fonksiyona yalnızca
    # ACTIVE (dolayısıyla her zaman bir bırakış tarihi belirlenmiş) kiralamalar
    # gelir — bu invariant'ı açıkça doğrular (sessizce varsaymak yerine).
    assert rental.ended_at is not None, "Aktif bir kiralamanın ended_at'i ayarlı olmalı"
    total_days = max((rental.ended_at - rental.started_at).days, 1)
    if rental.quoted_total:
        return Decimal(rental.quoted_total) / total_days

    daily = current_daily_cost(rental.vehicle)
    if daily is not None:
        return Decimal(str(daily))
    return Decimal("0")


def compute_return_settlement(rental: Rental, actual_return_at: datetime) -> ReturnSettlement:
    """Sözleşme dönüş zamanı ile fiili teslim zamanını karşılaştırıp farkı hesaplar.

    Karşılaştırma her zaman ``original_ended_at`` (uzatmayla değişmeyen ilk
    sözleşme tarihi) baz alınarak yapılır. Uzatılmamış kiralamalarda
    ``ended_at == original_ended_at`` olduğu için sonuç eski davranışla
    birebir aynıdır. Uzatılmışsa, ``original_ended_at`` → ``ended_at``
    arası cezasız "planlı" süre olarak, ``ended_at`` sonrası (tolerans +
    ceza çarpanıyla) "plansız aşım" olarak ayrı hesaplanıp toplanır.

    DB'ye yazmaz — hem önizleme hem ``process_vehicle_return`` commit adımı
    tarafından çağrılan saf bir fonksiyondur.
    """
    assert rental.ended_at is not None, "Aktif bir kiralamanın ended_at'i ayarlı olmalı"
    daily_rate = _daily_rate(rental)
    original_ended_at = rental.original_ended_at or rental.ended_at
    planned_ended_at = rental.ended_at

    delta_hours = (actual_return_at - original_ended_at).total_seconds() / 3600

    if delta_hours < 0:
        unused_days = (original_ended_at - actual_return_at).days
        if unused_days > 0:
            refund = _money(daily_rate * unused_days)
            return ReturnSettlement(
                return_status=ReturnStatus.EARLY,
                unused_days=unused_days,
                overage_hours=0.0,
                daily_rate=_money(daily_rate),
                price_difference=-refund,
                message=(
                    f"Araç {unused_days} gün erken teslim edildi. "
                    f"İade edilecek tutar: ₺{refund:,.0f}".replace(",", ".")
                ),
            )
        return ReturnSettlement(
            return_status=ReturnStatus.ON_TIME,
            unused_days=0,
            overage_hours=0.0,
            daily_rate=_money(daily_rate),
            price_difference=Decimal("0"),
            message="Araç zamanında teslim edildi.",
        )

    planned_days = 0
    planned_charge = Decimal("0")
    if planned_ended_at > original_ended_at:
        effective_planned_return = min(actual_return_at, planned_ended_at)
        if effective_planned_return > original_ended_at:
            planned_days = (effective_planned_return - original_ended_at).days
            if planned_days > 0:
                planned_charge = _money(daily_rate * planned_days)

    overage_hours = 0.0
    overage_charge = Decimal("0")
    if actual_return_at > planned_ended_at:
        delta_over_hours = (actual_return_at - planned_ended_at).total_seconds() / 3600
        if delta_over_hours > LATE_GRACE_HOURS:
            extra_days = max(math.ceil((delta_over_hours - LATE_GRACE_HOURS) / 24), 1)
            overage_charge = _money(daily_rate * extra_days * LATE_PENALTY_MULTIPLIER)
            overage_hours = round(delta_over_hours, 1)

    total_charge = planned_charge + overage_charge
    if total_charge == 0:
        return ReturnSettlement(
            return_status=ReturnStatus.ON_TIME,
            unused_days=0,
            overage_hours=round(max(delta_hours, 0), 1) if planned_ended_at == original_ended_at else 0.0,
            daily_rate=_money(daily_rate),
            price_difference=Decimal("0"),
            message="Araç zamanında teslim edildi.",
        )

    if planned_charge > 0 and overage_charge > 0:
        message = (
            f"Araç uzatılan süre ({planned_days} gün) sonrasında {round(delta_over_hours)} saat "
            f"daha rötar yaptı. Ek tahsil edilecek tutar: ₺{total_charge:,.0f}".replace(",", ".")
        )
    elif planned_charge > 0:
        message = (
            f"Araç uzatılan teslim tarihine kadar kullanıldı ({planned_days} gün ek süre). "
            f"Ek tahsil edilecek tutar: ₺{total_charge:,.0f}".replace(",", ".")
        )
    else:
        message = (
            f"Araç {round(delta_over_hours)} saat rötar yaptı. "
            f"Ek tahsil edilecek tutar: ₺{total_charge:,.0f}".replace(",", ".")
        )

    return ReturnSettlement(
        return_status=ReturnStatus.LATE,
        unused_days=0,
        overage_hours=overage_hours,
        daily_rate=_money(daily_rate),
        price_difference=total_charge,
        message=message,
    )


def extend_active_rental(rental: Rental, new_ended_at: datetime) -> Rental:
    """Aktif bir kiralamanın dönüş tarihini ileri öteler.

    ``original_ended_at`` (ilk sözleşme taahhüdü) hiç değişmez — yalnızca
    ``ended_at`` ileri taşınır, kiralama ötelenen tarihe kadar Aktif kalır.
    Aracın yeni tarih aralığında başka bir aktif kiralaması varsa uzatma
    reddedilir.
    """
    if rental.status != RentalStatus.ACTIVE:
        raise ValidationError({"error": "Yalnızca aktif kiralamalar uzatılabilir."})
    assert rental.ended_at is not None, "Aktif bir kiralamanın ended_at'i ayarlı olmalı"
    if new_ended_at <= rental.ended_at:
        raise ValidationError(
            {"error": "Yeni tarih, mevcut bırakış tarihinden sonra olmalıdır."}
        )

    conflict = (
        rental.vehicle.rentals.filter(
            status=RentalStatus.ACTIVE,
            started_at__lt=new_ended_at,
            ended_at__gt=rental.ended_at,
        )
        .exclude(pk=rental.pk)
        .exists()
    )
    if conflict:
        raise ValidationError(
            {"error": "Bu araç için seçilen tarihte başka bir kiralama var, uzatma yapılamaz."}
        )

    if rental.original_ended_at is None:
        rental.original_ended_at = rental.ended_at
    rental.ended_at = new_ended_at
    rental.save(update_fields=["ended_at", "original_ended_at"])
    return rental


@transaction.atomic
def process_vehicle_return(
    rental: Rental,
    actual_return_at: datetime,
    notes: str = "",
    *,
    preview: bool = False,
) -> ReturnSettlement:
    """Teslim farkını hesaplar; ``preview=False`` ise kalıcı olarak kapatır.

    Kapatma: Rental → COMPLETED, Vehicle → AVAILABLE (aynı anda — takvimdeki
    çakışma kontrolleri yalnızca ACTIVE kayıtlara baktığı için araç otomatik
    olarak yeni kiralamalara açılır), fark varsa RentalIncome ayarlama
    kaydı, sürücü geçmiş istatistiklerinin senkronizasyonu.
    """
    if not preview:
        # Yarış durumu koruması: satırı KİLİTLE ve durumu TEKRAR kontrol et.
        # Kilit olmadan, aynı kiralama için eşzamanlı iki "teslim al" isteği
        # ikisi de ACTIVE görüp ikisi de bu fonksiyonu tamamlayabilirdi —
        # @transaction.atomic tek başına bunu ENGELLEMEZ (yalnızca "hepsi ya
        # da hiçbiri" garantisi verir, eşzamanlı İKİ transaction'ın ikisinin
        # de çalışmasını değil) — sonuç: ÇİFT RentalIncome kaydı (gerçek
        # parasal çift düzeltme) ve tutarsız araç durumu.
        rental = Rental.objects.select_for_update().get(pk=rental.pk)
        if rental.status != RentalStatus.ACTIVE:
            raise ValidationError(
                {"error": "Bu kiralama zaten teslim alınmış veya iptal edilmiş."}
            )

    settlement = compute_return_settlement(rental, actual_return_at)
    if preview:
        return settlement

    rental.actual_return_at = actual_return_at
    rental.return_status = settlement.return_status
    rental.price_difference = settlement.price_difference
    rental.status = RentalStatus.COMPLETED
    rental.save(
        update_fields=["actual_return_at", "return_status", "price_difference", "status"]
    )

    rental.vehicle.status = VehicleStatus.AVAILABLE
    rental.vehicle.save(update_fields=["status"])

    if settlement.price_difference != 0:
        assert rental.ended_at is not None, "Aktif bir kiralamanın ended_at'i ayarlı olmalı"
        window_start = min(rental.ended_at, actual_return_at).date()
        window_end = max(rental.ended_at, actual_return_at).date()
        if settlement.return_status == ReturnStatus.LATE:
            RentalIncome.objects.create(
                vehicle=rental.vehicle,
                rental=rental,
                start_date=window_start,
                end_date=window_end,
                base_amount=Decimal("0"),
                late_fee=settlement.price_difference,
                notes=(notes or "Geç teslimat ek ücreti").strip(),
            )
        else:
            RentalIncome.objects.create(
                vehicle=rental.vehicle,
                rental=rental,
                start_date=window_start,
                end_date=window_end,
                base_amount=-abs(settlement.price_difference),
                notes=(notes or "Erken teslimat iadesi").strip(),
            )

    sync_rental_history_stats(rental.driver)
    # Sürücünün risk skoru artık "canlı" — sadece sürücü eklenirken bir kez
    # değil, her kiralama tamamlandığında güncel davranışına göre yeniden
    # hesaplanır (yukarıdaki sync ile tazelenen total_rentals/late_return_
    # count gibi istatistikler skora böylece gerçekten yansır).
    DriverEvaluationService().evaluate(rental.driver)
    return settlement
