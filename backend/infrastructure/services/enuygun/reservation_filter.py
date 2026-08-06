"""Enuygun rezervasyonlarını filo aracına göre filtreler ve normalize eder.

İki BAĞIMSIZ eşleştirme yöntemi vardır — biri diğerinin yedeği değildir,
ikisi de her araç için ayrı ayrı çalıştırılır ve ayrı ayrı raporlanır:

* **SIPP eşleşmesi** (``build_sipp_report``) — filo aracı ve ilan için
  gerçek özniteliklerden (marka/model, kasa, vites, yakıt) uluslararası
  standarda uygun bir SIPP kodu türetilir (bkz. ``sipp_service.py``);
  ikisinin segmenti (sınıf+kasa) aynıysa eşleşir. Ne bizim Ziraat'ten
  gelen ``vehicle.sipp_code``'umuz ne de Enuygun'un kendi gönderdiği kod
  hiçbir noktada kullanılmaz — ikisi de tedarikçi/manuel giriş kaynaklı
  ve güvenilmez.
* **TSB Tip Kodu eşleşmesi** (``build_tsb_type_code_report``) — filo
  aracı ve ilan, TSB Kasko Değer Listesi'ndeki ``brand_code``/``type_code``
  üzerinden çözümlenir; ikisi BİREBİR aynıysa eşleşir (tolerans/bant yok).
  Taraflardan biri TSB'de çözülemezse o araç için bu yöntemden sonuç
  çıkmaz — değer-bandı gibi bir yedek mekanizma YOKTUR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.infrastructure.services.enuygun.statistics_calculator import (
    PriceStatistics,
    calculate_statistics,
    statistics_to_dict,
)
from backend.infrastructure.services.enuygun.vehicle_matching_service import VehicleMatchingService
from backend.infrastructure.services.sipp.segment_matcher import listing_sipp_for_reservation
from backend.infrastructure.services.sipp.sipp_service import (
    derive_international_sipp_for_vehicle,
    derive_sipp_from_reservation_vehicle,
    sipp_codes_match,
)

MATCH_BASIS_SIPP = "SIPP"
MATCH_BASIS_TSB_TYPE = "TSB_TYPE_CODE"


@dataclass(frozen=True)
class MatchedVehicle:
    provider: str
    brand: str
    model: str
    vehicle_class: str
    segment: str
    daily_price: float
    reference_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "brand": self.brand,
            "model": self.model,
            "vehicleClass": self.vehicle_class,
            "segment": self.segment,
            "dailyPrice": self.daily_price,
        }


@dataclass(frozen=True)
class MarketSegmentReport:
    matched_segment: str
    match_basis: str
    vehicle_count: int
    matched_vehicles: list[MatchedVehicle]
    statistics: PriceStatistics | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "matchedSegment": self.matched_segment,
            "matchBasis": self.match_basis,
            "vehicleCount": self.vehicle_count,
            "matchedVehicles": [row.to_dict() for row in self.matched_vehicles],
            "statistics": statistics_to_dict(self.statistics),
        }


def _empty_report(match_basis: str) -> MarketSegmentReport:
    return MarketSegmentReport(
        matched_segment="",
        match_basis=match_basis,
        vehicle_count=0,
        matched_vehicles=[],
        statistics=calculate_statistics([]),
    )


def _parse_reservation(reservation: dict) -> MatchedVehicle | None:
    vehicle = reservation.get("vehicle") or {}
    company = reservation.get("company") or {}
    price = reservation.get("price") or {}

    daily_raw = price.get("dailyPrice")
    if daily_raw is None:
        return None
    try:
        daily_price = float(daily_raw)
    except (TypeError, ValueError):
        return None
    if daily_price <= 0:
        return None

    provider = (company.get("name") or reservation.get("provider") or "").strip()
    if not provider:
        return None

    return MatchedVehicle(
        provider=provider,
        brand=(vehicle.get("brand") or "").strip(),
        model=(vehicle.get("name") or "").strip(),
        vehicle_class=(vehicle.get("class") or "").strip(),
        segment=listing_sipp_for_reservation(reservation),
        daily_price=round(daily_price, 2),
        reference_id=(reservation.get("referenceId") or "").strip(),
    )


class ReservationFilter:
    """API'den gelen rezervasyonları SIPP ve TSB tip kodu yöntemleriyle süzer."""

    def __init__(self, matching_service: VehicleMatchingService | None = None) -> None:
        # Aynı snapshot'ı birden fazla filo aracı için süzerken TSB
        # değerlemeleri/tip kodları önbellekte kalsın diye servis dışarıdan
        # paylaşılabilir.
        self._matching = matching_service or VehicleMatchingService()

    def build_sipp_report(self, reservations: list[dict], vehicle) -> MarketSegmentReport:
        fleet_sipp = derive_international_sipp_for_vehicle(vehicle)
        matched = self._filter_by_sipp(reservations, fleet_sipp)
        return MarketSegmentReport(
            matched_segment=fleet_sipp,
            match_basis=MATCH_BASIS_SIPP,
            vehicle_count=len(matched),
            matched_vehicles=matched,
            statistics=calculate_statistics([row.daily_price for row in matched]),
        )

    def build_tsb_type_code_report(self, reservations: list[dict], vehicle) -> MarketSegmentReport:
        fleet_match = self._matching.type_code_for_fleet_vehicle(vehicle)
        if fleet_match is None:
            # TSB'de çözülemeyen filo aracı için bu yöntemden sonuç çıkmaz —
            # değer-bandı gibi bir yedek mekanizma yok (kullanıcı kararı).
            return _empty_report(MATCH_BASIS_TSB_TYPE)

        # İlan adayları filo aracının ÜRETİM YILIYLA aynı yılda çözülmeli —
        # TSB tip kodu yıla göre değişir, farklı yıl karşılaştırması hiçbir
        # zaman örtüşmez (bkz. type_codes_for_listing docstring'i).
        matched = self._filter_by_type_code(reservations, fleet_match.key, year=vehicle.production_year)
        label = f"{fleet_match.brand_name} {fleet_match.type_name}".strip()
        return MarketSegmentReport(
            matched_segment=label,
            match_basis=MATCH_BASIS_TSB_TYPE,
            vehicle_count=len(matched),
            matched_vehicles=matched,
            statistics=calculate_statistics([row.daily_price for row in matched]),
        )

    # -- eşleştirme modları ------------------------------------------------------

    def _filter_by_sipp(self, reservations: list[dict], fleet_sipp: str) -> list[MatchedVehicle]:
        matched: list[MatchedVehicle] = []
        seen_refs: set[str] = set()

        for reservation in reservations:
            vehicle = reservation.get("vehicle") or {}
            listing_sipp = derive_sipp_from_reservation_vehicle(vehicle)
            if not sipp_codes_match(fleet_sipp, listing_sipp):
                continue
            parsed = _parse_reservation(reservation)
            if parsed is None:
                continue
            if self._is_duplicate(parsed, seen_refs):
                continue
            matched.append(parsed)

        return matched

    def _filter_by_type_code(
        self, reservations: list[dict], fleet_key: tuple[int, int], *, year: int
    ) -> list[MatchedVehicle]:
        matched: list[MatchedVehicle] = []
        seen_refs: set[str] = set()

        for reservation in reservations:
            parsed = _parse_reservation(reservation)
            if parsed is None:
                continue
            # İlan başlığı donanım belirtmediği için tek bir tip koduna değil
            # birden fazla olası adaya çözülebilir (bkz. type_codes_for_listing);
            # filo aracının kodu bu adaylardan HERHANGİ biriyse eşleşme sayılır.
            candidates = self._matching.type_codes_for_listing(parsed.brand, parsed.model, year=year)
            if fleet_key not in {c.key for c in candidates}:
                continue
            if self._is_duplicate(parsed, seen_refs):
                continue
            matched.append(parsed)

        return matched

    @staticmethod
    def _is_duplicate(parsed: MatchedVehicle, seen_refs: set[str]) -> bool:
        ref = (parsed.reference_id or "").strip()
        if not ref:
            return False
        if ref in seen_refs:
            return True
        seen_refs.add(ref)
        return False
