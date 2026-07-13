"""SIPP tabanlı segment eşleştirme — filo aracı ile Enuygun teklifini eşler."""

from __future__ import annotations

from dataclasses import dataclass

from backend.infrastructure.services.sipp.sipp_service import (
    derive_sipp_from_reservation_vehicle,
    resolve_sipp,
    sipp_codes_match,
)


@dataclass(frozen=True)
class FleetVehicleProfile:
    brand: str
    model: str
    sipp_code: str


def fleet_profile_from_vehicle(vehicle) -> FleetVehicleProfile:
    profile = resolve_sipp(vehicle.brand, vehicle.model, vehicle.sipp_code or None)
    return FleetVehicleProfile(
        brand=vehicle.brand,
        model=vehicle.model,
        sipp_code=profile.code,
    )


def reservation_matches_segment(
    reservation: dict,
    target: FleetVehicleProfile,
) -> bool:
    """Enuygun teklifi filo aracının SIPP segmentiyle uyuşuyor mu?

    Enuygun ``sippCode`` çoğu zaman boş gelir; marka/model + yakıt + vites
    ile türetilen kod filo aracının SIPP segmentiyle (ilk 2 harf) karşılaştırılır.
    """
    vehicle = reservation.get("vehicle") or {}
    listing_sipp = derive_sipp_from_reservation_vehicle(vehicle)
    target_code = (target.sipp_code or "????").upper().ljust(4, "?")[:4]
    return sipp_codes_match(target_code, listing_sipp)


def matched_segment_label(target: FleetVehicleProfile) -> str:
    return (target.sipp_code or "????").upper().ljust(4, "?")[:4]


def listing_sipp_for_reservation(reservation: dict) -> str:
    """Tek rezervasyon için türetilmiş SIPP kodu."""
    return derive_sipp_from_reservation_vehicle(reservation.get("vehicle") or {})