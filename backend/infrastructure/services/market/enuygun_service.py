"""Enuygun araç kiralama arama API istemcisi.

Tek endpoint: POST https://cr-search.enuygun.com/api/v1/search
Tüm sayfalar gezilerek ``reservations`` listesi eksiksiz toplanır.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from backend.infrastructure.services.common.date_helper import RentalDateWindow, rental_window

logger = logging.getLogger(__name__)

SEARCH_URL = "https://cr-search.enuygun.com/api/v1/search"
DEFAULT_LOCATION = "ankara-merkez"
LOCATION_LABEL = "Ankara"
DEFAULT_DRIVER_AGE = 30
DEFAULT_PAGE_LIMIT = 50
REQUEST_TIMEOUT_SEC = 90

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.enuygun.com",
    "Referer": "https://www.enuygun.com/arac-kiralama/sehir/ankara/",
}


@dataclass
class EnuygunSearchResult:
    """Tek arama oturumunun ham sonucu."""

    reservations: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    pages_fetched: int = 0
    date_window: RentalDateWindow | None = None
    errors: list[str] = field(default_factory=list)


class EnuygunService:
    """Enuygun CR Search API — pagination dahil tüm rezervasyonları çeker."""

    def __init__(
        self,
        *,
        location: str = DEFAULT_LOCATION,
        driver_age: int = DEFAULT_DRIVER_AGE,
        page_limit: int = DEFAULT_PAGE_LIMIT,
        timeout_sec: int = REQUEST_TIMEOUT_SEC,
    ) -> None:
        self.location = location
        self.driver_age = driver_age
        self.page_limit = page_limit
        self.timeout_sec = timeout_sec

    def build_search_payload(
        self,
        *,
        date_window: RentalDateWindow,
        page: int,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return {
            "pickUpLocation": self.location,
            "dropOffLocation": self.location,
            "pickUpDate": date_window.pickup_date_iso,
            "dropOffDate": date_window.dropoff_date_iso,
            "pickUpTime": date_window.pickup_time,
            "dropOffTime": date_window.dropoff_time,
            "driverAge": self.driver_age,
            "pagination": {
                "page": page,
                "limit": limit or self.page_limit,
            },
        }

    def search_page(
        self,
        *,
        date_window: RentalDateWindow,
        page: int = 1,
        limit: int | None = None,
    ) -> dict[str, Any]:
        payload = self.build_search_payload(
            date_window=date_window,
            page=page,
            limit=limit,
        )
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            SEARCH_URL,
            data=body,
            headers=_DEFAULT_HEADERS,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Enuygun API HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Enuygun API bağlantı hatası: {exc.reason}") from exc

        if raw.get("status") != "OK":
            message = raw.get("userMessage") or raw.get("message") or "Bilinmeyen hata"
            raise RuntimeError(f"Enuygun API hatası: {message}")

        data = raw.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Enuygun API beklenmeyen yanıt formatı")

        return data

    def fetch_all_reservations(
        self,
        *,
        date_window: RentalDateWindow | None = None,
    ) -> EnuygunSearchResult:
        """Pagination ile tüm ``reservations`` kayıtlarını toplar."""
        window = date_window or rental_window()
        result = EnuygunSearchResult(date_window=window)
        page = 1
        total: int | None = None

        while True:
            try:
                data = self.search_page(date_window=window, page=page)
            except RuntimeError as exc:
                result.errors.append(str(exc))
                logger.exception("Enuygun sayfa %s alınamadı", page)
                break

            batch = data.get("reservations") or []
            pagination = data.get("pagination") or {}
            if total is None:
                total = int(pagination.get("total") or 0)
                result.total_count = total

            result.reservations.extend(batch)
            result.pages_fetched = page

            if not batch:
                break
            if total and len(result.reservations) >= total:
                break

            page += 1
            if page > 500:
                result.errors.append("Pagination güvenlik limiti aşıldı (500 sayfa).")
                break

        if total and len(result.reservations) < total:
            result.errors.append(
                f"Eksik veri: {len(result.reservations)}/{total} rezervasyon alındı."
            )

        result.reservations = _dedupe_reservations(result.reservations)

        return result


def _dedupe_reservations(reservations: list[dict]) -> list[dict]:
    """Pagination örtüşmesinden kaynaklanan tekrarları ``referenceId`` ile eler."""
    seen: set[str] = set()
    unique: list[dict] = []
    for reservation in reservations:
        ref = (reservation.get("referenceId") or "").strip()
        if ref:
            if ref in seen:
                continue
            seen.add(ref)
        unique.append(reservation)
    return unique