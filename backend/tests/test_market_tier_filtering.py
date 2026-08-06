"""SIPP eşleşmesi ve TSB Tip Kodu eşleşmesi — iki BAĞIMSIZ yöntem testleri.

Artık kasko değer-bandı (0.65×–1.50×) yöntemi yok; TSB tarafı tip koduna
göre BİREBİR eşleşiyor, SIPP tarafı da gerçek özniteliklerden (marka/model,
vites, yakıt) türetilen uluslararası koda göre eşleşiyor — ikisi de
tedarikçi/manuel girişli ham kodlara (Ziraat sipp_code, Enuygun sippCode)
hiç bakmıyor.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.apps.companies.models import Company
from backend.apps.enuygun.models import CarValuation
from backend.apps.vehicles.choices import FuelType, Transmission
from backend.apps.vehicles.models import Vehicle, VehicleStatus
from backend.infrastructure.services.enuygun.reservation_filter import (
    MATCH_BASIS_SIPP,
    MATCH_BASIS_TSB_TYPE,
    ReservationFilter,
)

pytestmark = pytest.mark.django_db


def _reservation(
    ref: str,
    brand: str,
    model: str,
    daily_price: float,
    *,
    sipp: str = "ZZZZ",
    fuel: str = "Dizel",
    transmission: str = "Otomatik",
) -> dict:
    """Enuygun API formatında test rezervasyonu."""
    return {
        "referenceId": ref,
        "vehicle": {
            "brand": brand,
            "name": model,
            "class": "",
            "fuel": fuel,
            "transmission": transmission,
            # Kasıtlı olarak saçma bir kod — artık hiçbir eşleşme yönteminde kullanılmıyor.
            "sippCode": sipp,
        },
        "company": {"name": "TestRent"},
        "price": {"dailyPrice": daily_price, "currency": "TRY"},
    }


@pytest.fixture
def egea(company: Company) -> Vehicle:
    # Ziraat'ten gelen sipp_code KASITLI OLARAK gerçek sınıfıyla uyuşmuyor
    # (Egea aslında kompakt bir dizel otomatik hatch/sedan) — hiçbir
    # eşleştirme yönteminin bunu kullanmadığını doğrulamak için.
    return Vehicle.objects.create(
        company=company,
        plate_number="06TIER01",
        brand="Fiat",
        model="Egea",
        production_year=2023,
        current_km=30_000,
        status=VehicleStatus.AVAILABLE,
        sipp_code="ZZZZ",
        fuel_type=FuelType.DIESEL,
        transmission=Transmission.AUTOMATIC,
    )


@pytest.fixture
def valuations() -> None:
    rows = [
        ("TOFAS-FIAT", "EGEA 1.4 FIRE LOUNGE", 2023, "1300000", 52, 3),
        ("TOFAS-FIAT", "EGEA CROSS 1.5 MULTIJET", 2023, "1450000", 52, 9),
        ("BMW", "520I M SPORT", 2023, "8000000", 7, 4),
    ]
    CarValuation.objects.bulk_create(
        CarValuation(
            brand_code=brand_code,
            type_code=type_code,
            brand_name=brand,
            type_name=type_name,
            year=year,
            kasko_value=Decimal(value),
        )
        for brand, type_name, year, value, brand_code, type_code in rows
    )


def test_sipp_report_matches_same_class_and_excludes_premium_brand(egea, valuations) -> None:
    reservations = [
        # Aynı sınıf (kompakt/hatch-sedan, dizel, otomatik) — tedarikçinin
        # gönderdiği sippCode tamamen saçma olsa bile eşleşmeli.
        _reservation("r1", "Renault", "Megane ve benzeri", 1500.0, sipp="XXXX"),
        # Premium marka (BMW) farklı sınıfa düşer — Ziraat/Enuygun kodu ne
        # olursa olsun eşleşmemeli.
        _reservation("r2", "BMW", "520i ve benzeri", 9000.0, sipp="ECMR", fuel="Benzin"),
    ]

    report = ReservationFilter().build_sipp_report(reservations, egea)

    assert report.match_basis == MATCH_BASIS_SIPP
    included = {row.reference_id for row in report.matched_vehicles}
    assert included == {"r1"}


def test_tsb_type_code_requires_exact_catalog_match_not_just_similar_value(egea, valuations) -> None:
    # EGEA CROSS 1.5 MULTIJET (1.45M ₺) değeri EGEA 1.4 FIRE LOUNGE'a
    # (1.3M ₺) yeterince yakın olurdu (eski değer-bandı yöntemiyle
    # eşleşirdi) ama TSB tip kodu FARKLI (3 vs 9) — artık eşleşmemeli.
    reservations = [
        _reservation("r1", "Fiat", "Egea 1.4 Fire Lounge", 1500.0),
        _reservation("r2", "Fiat", "Egea Cross 1.5 Multijet", 1600.0),
    ]

    report = ReservationFilter().build_tsb_type_code_report(reservations, egea)

    assert report.match_basis == MATCH_BASIS_TSB_TYPE
    included = {row.reference_id for row in report.matched_vehicles}
    assert included == {"r1"}


def test_tsb_type_code_has_no_fallback_when_fleet_vehicle_unresolved(company: Company) -> None:
    # CarValuation tablosunda hiç kaydı olmayan bir marka/model: TSB tip
    # kodu çözülemez. Eski sistemde bu durumda SIPP'e düşülürdü — artık
    # yöntemler bağımsız olduğu için burada hiçbir yedek YOK, boş rapor döner.
    vehicle = Vehicle.objects.create(
        company=company,
        plate_number="06TIER02",
        brand="Acme",
        model="Roadster",
        production_year=2023,
        current_km=10_000,
        status=VehicleStatus.AVAILABLE,
    )
    reservations = [_reservation("r1", "Acme", "Roadster", 1400.0)]

    report = ReservationFilter().build_tsb_type_code_report(reservations, vehicle)

    assert report.match_basis == MATCH_BASIS_TSB_TYPE
    assert report.vehicle_count == 0
    assert report.matched_vehicles == []


def test_same_reservation_can_match_both_methods_independently(egea, valuations) -> None:
    # Aynı ilan hem SIPP hem TSB tip koduyla eşleşebilir — biri diğerini
    # "duplicate" sayıp elemez, iki bağımsız raporda da sayılır.
    reservations = [_reservation("r1", "Fiat", "Egea 1.4 Fire Lounge", 1500.0)]

    sipp_report = ReservationFilter().build_sipp_report(reservations, egea)
    tsb_report = ReservationFilter().build_tsb_type_code_report(reservations, egea)

    assert {row.reference_id for row in sipp_report.matched_vehicles} == {"r1"}
    assert {row.reference_id for row in tsb_report.matched_vehicles} == {"r1"}


def test_same_reference_not_double_counted_within_one_report(egea, valuations) -> None:
    reservations = [
        _reservation("r1", "Fiat", "Egea 1.4 Fire Lounge", 1500.0),
        _reservation("r1", "Fiat", "Egea 1.4 Fire Lounge", 1500.0),
    ]

    report = ReservationFilter().build_sipp_report(reservations, egea)

    assert report.vehicle_count == 1


def test_sipp_report_statistics_only_from_matched_listings(egea, valuations) -> None:
    # Megane ve Golf, Egea ile aynı SIPP segmentinde (CD, _MODEL_PROFILES'ta
    # ikisi de CDMR) — ikisi de eşleşmeli. BMW farklı sınıfa düştüğü için dışarıda kalmalı.
    reservations = [
        _reservation("r1", "Renault", "Megane ve benzeri", 1500.0),
        _reservation("r2", "Volkswagen", "Golf ve benzeri", 1700.0),
        _reservation("r3", "BMW", "520i ve benzeri", 9000.0, fuel="Benzin"),
    ]

    report = ReservationFilter().build_sipp_report(reservations, egea)

    assert report.statistics is not None
    assert report.statistics.min_price == 1500.0
    assert report.statistics.max_price == 1700.0
    assert report.statistics.average_price == 1600.0
