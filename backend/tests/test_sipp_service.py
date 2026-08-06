"""SIPP kodu türetme — ne Ziraat'in ne Enuygun'un ham koduna güvenilmez."""

from __future__ import annotations

import pytest

from backend.apps.companies.models import Company
from backend.apps.vehicles.choices import FuelType, Transmission
from backend.apps.vehicles.models import Vehicle, VehicleStatus
from backend.infrastructure.services.sipp.sipp_service import (
    derive_international_sipp_for_vehicle,
    derive_sipp_from_listing,
    resolve_sipp,
    sipp_codes_match,
)

pytestmark = pytest.mark.django_db


def _vehicle(company: Company, **overrides) -> Vehicle:
    defaults = dict(
        company=company,
        plate_number="06SIPP01",
        brand="Renault",
        model="Clio",
        production_year=2023,
        current_km=1000,
        status=VehicleStatus.AVAILABLE,
    )
    defaults.update(overrides)
    return Vehicle.objects.create(**defaults)


def test_derive_sipp_from_listing_ignores_unreliable_api_sipp_code() -> None:
    # Enuygun'un kendi gönderdiği sippCode artık parametre olarak bile
    # alınmıyor (fonksiyon imzasından kaldırıldı) — kod her zaman gerçek
    # marka/model + vites + yakıttan türetilir.
    code = derive_sipp_from_listing(
        "Renault", "Clio ve benzeri", fuel="Dizel", transmission="Otomatik"
    )
    assert code == "ECAD"


def test_derive_international_sipp_ignores_stored_ziraat_code(company: Company) -> None:
    # Ziraat'ten gelen sipp_code kasıtlı olarak yanlış/tutarsız (aracın
    # gerçek sınıfıyla alakasız) — türetilen kod buna hiç bakmamalı.
    vehicle = _vehicle(
        company,
        sipp_code="XXXX",
        fuel_type=FuelType.DIESEL,
        transmission=Transmission.AUTOMATIC,
    )
    intl = derive_international_sipp_for_vehicle(vehicle)
    assert intl != "XXXX"
    # Renault Clio -> _MODEL_PROFILES'ta ECMR (sınıf E, kasa C); gerçek
    # vites/yakıt (otomatik+dizel) -> AD.
    assert intl == "ECAD"


def test_derive_international_sipp_uses_real_transmission_and_fuel(company: Company) -> None:
    manual_petrol = _vehicle(
        company,
        plate_number="06SIPP02",
        fuel_type=FuelType.GASOLINE,
        transmission=Transmission.MANUAL,
    )
    auto_electric = _vehicle(
        company,
        plate_number="06SIPP03",
        fuel_type=FuelType.ELECTRIC,
        transmission=Transmission.AUTOMATIC,
    )
    assert derive_international_sipp_for_vehicle(manual_petrol)[2:] == "MR"
    assert derive_international_sipp_for_vehicle(auto_electric)[2:] == "AE"


def test_unknown_premium_brand_gets_premium_class_not_generic_default(company: Company) -> None:
    # Mercedes/BMW/Audi... _MODEL_PROFILES tablosunda yok; markaya
    # bakmadan jenerik "C" (Kompakt) varsayılanına düşerse örn. bir BMW
    # 520i ekonomik bir hatchback ile aynı sepete girer (gerçek bug, bu
    # test bunu kilitler).
    vehicle = _vehicle(
        company,
        brand="BMW",
        model="520i",
        fuel_type=FuelType.GASOLINE,
        transmission=Transmission.AUTOMATIC,
    )
    intl = derive_international_sipp_for_vehicle(vehicle)
    assert intl[0] == "P"


def test_unknown_premium_brand_listing_also_gets_premium_class() -> None:
    # Aynı düzeltme Enuygun ilanı tarafında da geçerli olmalı — aksi halde
    # bir BMW ilanı hâlâ jenerik "Kompakt" sepetine düşüp ekonomik bir
    # filo aracıyla yanlışlıkla eşleşebilir (bkz. reservation_filter testleri).
    code = derive_sipp_from_listing(
        "BMW", "520i ve benzeri", vehicle_class="", fuel="Benzin", transmission="Otomatik"
    )
    assert code[0] == "P"


def test_resolve_sipp_still_shows_vehicles_own_stored_code(company: Company) -> None:
    # resolve_sipp() DEĞİŞMEDİ — Araçlar sayfasındaki "SIPP" alanı hâlâ
    # Ziraat'ten gelen kodu olduğu gibi gösterir, eşleştirme bundan
    # etkilenmez.
    vehicle = _vehicle(company, sipp_code="XXXX")
    profile = resolve_sipp(vehicle.brand, vehicle.model, vehicle.sipp_code or None)
    assert profile.code == "XXXX"


def test_sipp_codes_match_compares_class_and_body_only() -> None:
    assert sipp_codes_match("ECMR", "ECAD")
    assert not sipp_codes_match("ECMR", "PDAD")
