"""Filo envanterinin toplu Excel (.xlsx) raporunu üreten servis.

Fleet Management ekranındaki araç listesini (plaka, durum, km, maliyet,
kârlılık vb.) tek bir tabloda toplar. Günlük maliyet ve biriken net kâr
``rental_economics_service``'ten okunur; böylece Excel'deki rakamlar
uygulama içindeki maliyet kartlarıyla birebir aynıdır.
"""

from __future__ import annotations

from collections.abc import Iterable

from backend.apps.vehicles.models import Vehicle, VehicleStatus
from backend.infrastructure.services.cost_calculation.rental_economics_service import (
    build_vehicle_profit_summary,
    current_daily_cost,
)
from backend.infrastructure.services.reporting.excel import (
    CURRENCY_FORMAT,
    KM_FORMAT,
    build_worksheet_bytes,
)
from backend.infrastructure.services.sipp.sipp_service import decode_sipp, resolve_sipp

_STATUS_TR: dict[str, str] = {
    VehicleStatus.AVAILABLE: "Müsait",
    VehicleStatus.RENTED: "Kirada",
    VehicleStatus.MAINTENANCE: "Bakımda",
    VehicleStatus.SOLD: "Satıldı",
}

_HEADERS: tuple[str, ...] = (
    "Plaka",
    "Marka / Model",
    "Durum",
    "Model Yılı",
    "Kilometre",
    "Yakıt Tipi",
    "Şanzıman",
    "Sınıf / SIPP Kodu",
    "Alış Fiyatı (₺)",
    "Günlük Maliyet (₺)",
    "Biriken Net Kâr (₺)",
)

# 1 tabanlı sütun numaraları (_HEADERS sırasıyla).
_NUMBER_FORMATS: dict[int, str] = {
    5: KM_FORMAT,
    9: CURRENCY_FORMAT,
    10: CURRENCY_FORMAT,
    11: CURRENCY_FORMAT,
}


def _vehicle_row(vehicle: Vehicle) -> tuple[object, ...]:
    sipp = resolve_sipp(vehicle.brand, vehicle.model, vehicle.sipp_code or None)
    daily_cost = current_daily_cost(vehicle)
    profit = build_vehicle_profit_summary(vehicle)

    return (
        vehicle.plate_number,
        f"{vehicle.brand} {vehicle.model}".strip(),
        _STATUS_TR.get(vehicle.status, vehicle.get_status_display()),
        vehicle.production_year,
        vehicle.current_km,
        vehicle.get_fuel_type_display() if vehicle.fuel_type else "—",
        vehicle.get_transmission_display() if vehicle.transmission else "—",
        f"{decode_sipp(sipp.code)['sinif']} / {sipp.code}",
        vehicle.purchase_price,
        daily_cost,
        profit["accumulated_profit"],
    )


def build_fleet_inventory_workbook(vehicles: Iterable[Vehicle]) -> bytes:
    """Verilen araç listesi için .xlsx dosya içeriği (bytes) üretir."""
    return build_worksheet_bytes(
        "Filo Envanteri",
        _HEADERS,
        (_vehicle_row(vehicle) for vehicle in vehicles),
        number_formats=_NUMBER_FORMATS,
    )
