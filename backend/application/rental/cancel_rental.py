"""Kiralama iptali — hem ``RentalCancelView`` hem AI asistanının
``cancel_rental`` tool'u tarafından çağrılan TEK iş mantığı kaynağı.

Bir kiralamayı iptal etmek iki farklı gerçek işlem anlamına gelir:
* Kiralama henüz BAŞLAMADIYSA (Gelecek): fiyat farkı olmadan doğrudan iptal.
* Kiralama zaten BAŞLADIYSA (Aktif): fiilen "erken teslim" demektir — fark
  hesaplanır (``process_vehicle_return``), kayıt CANCELLED değil COMPLETED
  olur. Bu ayrım burada, view'daki ile birebir aynı şekilde yapılır.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from backend.application.customer.rental_stats import sync_rental_history_stats
from backend.application.driver.evaluate_driver import DriverEvaluationService
from backend.application.rental.return_processing import ReturnSettlement, process_vehicle_return
from backend.apps.companies.models import CustomUser
from backend.apps.rentals.models import Rental, RentalStatus
from backend.common.audit import log_change


@dataclass
class CancelResult:
    rental: Rental
    early_return: bool
    settlement: ReturnSettlement | None = None


def cancel_rental(rental: Rental, *, cancelled_by: CustomUser, now: datetime | None = None) -> CancelResult:
    if rental.status != RentalStatus.ACTIVE:
        raise ValidationError({"error": "Yalnızca aktif kiralamalar iptal edilebilir."})

    now = now or timezone.now()
    if rental.started_at > now:
        with transaction.atomic():
            # Yarış durumu koruması: iki eşzamanlı iptal isteği ikisi de
            # ACTIVE görüp ikisi de işlemeyi tamamlamasın diye satır
            # kilitlenip durum tekrar kontrol edilir.
            locked_rental = Rental.objects.select_for_update().get(pk=rental.pk)
            if locked_rental.status != RentalStatus.ACTIVE:
                raise ValidationError({"error": "Yalnızca aktif kiralamalar iptal edilebilir."})
            locked_rental.status = RentalStatus.CANCELLED
            locked_rental.save(update_fields=["status"])
            sync_rental_history_stats(locked_rental.driver)
            DriverEvaluationService().evaluate(locked_rental.driver)
            log_change(
                user=cancelled_by,
                obj=locked_rental,
                message="Kiralama iptal edildi (henüz başlamamıştı).",
            )
        return CancelResult(rental=locked_rental, early_return=False)

    settlement = process_vehicle_return(rental, now)
    rental.refresh_from_db()
    log_change(
        user=cancelled_by,
        obj=rental,
        message=f"Kiralama iptal edildi (erken teslim olarak işlendi): {settlement.message}",
    )
    return CancelResult(rental=rental, early_return=True, settlement=settlement)
