"""Enuygun rezervasyonundan denormalize SIPP etiketi üretimi.

Fiili SIPP EŞLEŞTİRME kararı (filo aracı ↔ ilan) artık doğrudan
``reservation_filter.py``'de, ``sipp_service.derive_international_sipp_for_vehicle``/
``derive_sipp_from_reservation_vehicle`` + ``sipp_codes_match`` ile veriliyor.
Bu modülde yalnızca, her rezervasyon için bilgi amaçlı (raporlama/önbellek)
SIPP etiketini üreten tek bir yardımcı kalıyor.
"""

from __future__ import annotations

from backend.infrastructure.services.sipp.sipp_service import derive_sipp_from_reservation_vehicle


def listing_sipp_for_reservation(reservation: dict) -> str:
    """Tek rezervasyon için türetilmiş SIPP kodu (bilgi amaçlı)."""
    return derive_sipp_from_reservation_vehicle(reservation.get("vehicle") or {})
