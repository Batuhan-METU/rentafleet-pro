"""Enuygun rezervasyonlarını filo aracına göre filtreler ve normalize eder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.infrastructure.services.sipp.segment_matcher import (
    FleetVehicleProfile,
    fleet_profile_from_vehicle,
    listing_sipp_for_reservation,
    matched_segment_label,
    reservation_matches_segment,
)
from backend.infrastructure.services.market.statistics_calculator import (
    PriceStatistics,
    calculate_statistics,
    statistics_to_dict,
)


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
    vehicle_count: int
    matched_vehicles: list[MatchedVehicle]
    statistics: PriceStatistics | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "matchedSegment": self.matched_segment,
            "vehicleCount": self.vehicle_count,
            "matchedVehicles": [row.to_dict() for row in self.matched_vehicles],
            "statistics": statistics_to_dict(self.statistics),
        }


def _parse_reservation(reservation: dict, fleet_segment: str) -> MatchedVehicle | None:
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

    brand = (vehicle.get("brand") or "").strip()
    model = (vehicle.get("name") or "").strip()
    vehicle_class = (vehicle.get("class") or "").strip()
    listing_sipp = listing_sipp_for_reservation(reservation)

    return MatchedVehicle(
        provider=provider,
        brand=brand,
        model=model,
        vehicle_class=vehicle_class,
        segment=listing_sipp,
        daily_price=round(daily_price, 2),
        reference_id=(reservation.get("referenceId") or "").strip(),
    )


class ReservationFilter:
    """API'den gelen tüm rezervasyonları segment kurallarına göre süzer."""

    def filter_for_profile(
        self,
        reservations: list[dict],
        profile: FleetVehicleProfile,
    ) -> list[MatchedVehicle]:
        segment_code = matched_segment_label(profile)
        matched: list[MatchedVehicle] = []
        seen_refs: set[str] = set()

        for reservation in reservations:
            if not reservation_matches_segment(reservation, profile):
                continue
            parsed = _parse_reservation(reservation, segment_code)
            if parsed is None:
                continue
            ref = (parsed.reference_id or "").strip()
            if ref:
                if ref in seen_refs:
                    continue
                seen_refs.add(ref)
            matched.append(parsed)

        return matched

    def build_report(
        self,
        reservations: list[dict],
        vehicle,
    ) -> MarketSegmentReport:
        profile = fleet_profile_from_vehicle(vehicle)
        matched = self.filter_for_profile(reservations, profile)
        prices = [row.daily_price for row in matched]
        return MarketSegmentReport(
            matched_segment=matched_segment_label(profile),
            vehicle_count=len(matched),
            matched_vehicles=matched,
            statistics=calculate_statistics(prices),
        )