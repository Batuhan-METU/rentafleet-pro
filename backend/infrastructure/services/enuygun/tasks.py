"""Celery görevleri — Enuygun piyasa fiyatı senkronu.

``fetch_competitor_prices`` yönetim komutuyla AYNI çekirdek fonksiyonu
(``sync_fleet_market_prices``) çağırır — komut CLI'dan tek şirket için
senkron tetikler, bu görev Celery Beat ile TÜM şirketler için periyodik/
asenkron tetikler (bkz. settings.CELERY_BEAT_SCHEDULE). İş mantığı tek
yerde yaşar; ikisi de onu sarmalar, birbirini sarmalamaz.
"""

from __future__ import annotations

import logging

from celery import shared_task

from backend.infrastructure.services.common.date_helper import rental_window
from backend.infrastructure.services.enuygun.comparable_vehicle_service import (
    sync_fleet_market_prices,
)

logger = logging.getLogger(__name__)


@shared_task(name="backend.infrastructure.services.enuygun.tasks.refresh_competitor_prices_task")
def refresh_competitor_prices_task(company_id: int | None = None) -> dict[int, dict]:
    """Bir (``company_id`` verilirse) ya da TÜM şirketler için piyasa fiyatını yeniler.

    Bir şirket için senkron başarısız olursa diğerlerini durdurmaz — hatası
    loglanır, sonuç sözlüğünde ``{"error": True}`` olarak işaretlenir.
    """
    from backend.apps.companies.models import Company

    company_ids = (
        [company_id]
        if company_id is not None
        else list(Company.objects.values_list("pk", flat=True))
    )
    window = rental_window()
    results: dict[int, dict] = {}
    for cid in company_ids:
        try:
            results[cid] = sync_fleet_market_prices(force=True, window=window, company_id=cid)
        except Exception:
            logger.exception("Şirket #%s için Enuygun piyasa fiyatı senkronu başarısız", cid)
            results[cid] = {"error": True}
    return results
