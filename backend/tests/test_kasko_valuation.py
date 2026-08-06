"""Kasko değer modeli: import komutu + VehicleMatchingService birim testleri."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.management import call_command
from openpyxl import Workbook

from backend.apps.enuygun.models import CarValuation
from backend.infrastructure.services.enuygun.vehicle_matching_service import (
    VALUATION_TIERS,
    VehicleMatchingService,
    normalize_listing_model,
    tier_for_value,
)

pytestmark = pytest.mark.django_db


def _require(value):
    """Test yardımcı fonksiyonu: None döndüğünde AssertionError ile netçe
    başarısız olur (mypy için de doğru daraltmayı sağlar)."""
    assert value is not None
    return value


# --- import_kasko_values ---------------------------------------------------


def _write_tsb_xlsx(path) -> None:
    """Gerçek TSB düzeninde küçük bir test dosyası üretir."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Temmuz 2026"])
    ws.append(["Marka Kodu", "Tip Kodu", "Marka Adı", "Tip Adı", 2026, 2025, 2024])
    ws.append([123, 2001, "RENAULT", "CLIO JOY 1.0 SCE 65", 0, 1_500_000, 1_400_000])
    ws.append([123, 2002, "RENAULT", "CLIO ICON 1.0 TCE", 1_700_000, 0, 0])
    ws.append([7, 3001, "BMW", "520I M SPORT", 0, 8_000_000, 0])
    ws.append([None, None, None, None, 0, 0, 0])  # bozuk satır atlanmalı
    wb.save(path)


def test_import_command_reshapes_wide_table_to_long_form(tmp_path) -> None:
    file_path = tmp_path / "tsb_test.xlsx"
    _write_tsb_xlsx(file_path)

    call_command("import_kasko_values", file=str(file_path))

    # 0 hücreleri atlanır: CLIO JOY (2 yıl) + CLIO ICON (1) + BMW (1) = 4 satır.
    assert CarValuation.objects.count() == 4
    joy_2025 = CarValuation.objects.get(type_code=2001, year=2025)
    assert joy_2025.brand_name == "RENAULT"
    assert joy_2025.kasko_value == Decimal("1500000")

    # Idempotent: ikinci çalıştırma kayıtları çoğaltmaz.
    call_command("import_kasko_values", file=str(file_path))
    assert CarValuation.objects.count() == 4


# --- normalizasyon ve tier sınırları ---------------------------------------


def test_listing_title_normalization() -> None:
    assert normalize_listing_model("Clio ve benzeri") == "CLIO"
    assert normalize_listing_model("Egea veya benzeri") == "EGEA"
    assert normalize_listing_model("Corolla (veya benzeri) vb.") == "COROLLA"
    assert normalize_listing_model("i20") == "I20"
    assert normalize_listing_model("") == ""


def test_tier_classification() -> None:
    assert tier_for_value(None) is None
    assert tier_for_value(0) is None
    assert _require(tier_for_value(Decimal("800000"))).number == 1
    assert _require(tier_for_value(Decimal("1199999.99"))).number == 1
    assert _require(tier_for_value(Decimal("1200000"))).number == 2
    assert _require(tier_for_value(Decimal("1999999"))).number == 2
    assert _require(tier_for_value(Decimal("2000000"))).number == 3
    assert _require(tier_for_value(Decimal("9500000"))).number == 3
    assert len(VALUATION_TIERS) == 3


# --- VehicleMatchingService -------------------------------------------------


@pytest.fixture
def valuations() -> None:
    rows = [
        # Clio 2022: iki donanım → medyan (950k + 1.05M) / 2 = 1.0M → Tier 1.
        (123, 1, "RENAULT", "CLIO JOY 1.0 SCE 65", 2022, "950000"),
        (123, 2, "RENAULT", "CLIO ICON 1.0 TCE 90", 2022, "1050000"),
        (123, 2, "RENAULT", "CLIO ICON 1.0 TCE 90", 2024, "1600000"),
        # Egea, TSB'de TOFAS-FIAT markası altında (marka token eşleşmesi).
        (52, 3, "TOFAS-FIAT", "EGEA 1.4 FIRE LOUNGE", 2023, "1300000"),
        # BMW üst segment.
        (7, 4, "BMW", "520I M SPORT", 2024, "8000000"),
        # CLIO'ya benzemesin diye farklı model: prefix karışma testi.
        (123, 5, "RENAULT", "CAPTUR 1.3 TCE", 2022, "1450000"),
    ]
    CarValuation.objects.bulk_create(
        CarValuation(
            brand_code=bc,
            type_code=tc,
            brand_name=bn,
            type_name=tn,
            year=year,
            kasko_value=Decimal(value),
        )
        for bc, tc, bn, tn, year, value in rows
    )


def test_year_based_median_valuation(valuations) -> None:
    svc = VehicleMatchingService()
    # 2022: iki donanımın medyanı.
    assert svc.valuation_for("Renault", "Clio", year=2022) == Decimal("1000000")
    # Tam yıl yoksa en yakın yıl (2023 → 2022 ve 2024 eşit uzaklıkta; yeni yıl önce).
    assert svc.valuation_for("Renault", "Clio", year=2023) == Decimal("1600000")
    # Yıl verilmezse (ilan) en güncel yıl.
    assert svc.valuation_for("Renault", "Clio ve benzeri") == Decimal("1600000")


def test_brand_token_matching_tofas_fiat(valuations) -> None:
    svc = VehicleMatchingService()
    assert svc.valuation_for("Fiat", "Egea", year=2023) == Decimal("1300000")


def test_unknown_model_returns_none(valuations) -> None:
    svc = VehicleMatchingService()
    assert svc.valuation_for("Renault", "Talisman", year=2022) is None
    assert svc.tier_for("Acme", "Roadster") is None


def test_brand_extracted_from_title_when_blank(valuations) -> None:
    # Tedarikçi markayı ayrı göndermemiş; tam başlık model alanında.
    svc = VehicleMatchingService()
    assert svc.valuation_for("", "Renault Clio ve benzeri") == Decimal("1600000")
    assert svc.valuation_for("", "Bilinmeyen Baslik") is None


def test_tier_assignment(valuations) -> None:
    svc = VehicleMatchingService()
    assert _require(svc.tier_for("Renault", "Clio", year=2022)).number == 1
    assert _require(svc.tier_for("Fiat", "Egea", year=2023)).number == 2
    assert _require(svc.tier_for("BMW", "520i veya benzeri")).number == 3


# --- TSB tip kodu (VehicleMatchingService.type_code_for) -------------------


def test_type_code_for_known_model_and_year(valuations) -> None:
    svc = VehicleMatchingService()
    match = _require(svc.type_code_for("Renault", "Clio", year=2024))
    assert match.key == (123, 2)
    assert match.brand_name == "RENAULT"
    assert "ICON" in match.type_name


def test_type_codes_for_listing_extracts_brand_from_title(valuations) -> None:
    # "TOFAS-FIAT" gibi birleşik marka adları başlık-önek eşleşmesine
    # girmez (bkz. _split_brand_from_title) — bu yüzden tek-tokenlı bir
    # marka (RENAULT) ile test edilir, valuation_for ile aynı davranış.
    svc = VehicleMatchingService()
    matches = svc.type_codes_for_listing("", "Renault Clio ve benzeri")
    assert (123, 2) in {m.key for m in matches}


def test_type_codes_for_listing_returns_all_plausible_trims(valuations) -> None:
    # "Clio" gibi donanım belirtmeyen genel bir sorgu, o yılki (2024) TÜM
    # eşleşen donanım satırlarına karşılık gelmeli — sadece birine değil.
    svc = VehicleMatchingService()
    matches = svc.type_codes_for_listing("Renault", "Clio")
    assert (123, 2) in {m.key for m in matches}


def test_type_codes_for_listing_unknown_model_returns_empty_list(valuations) -> None:
    svc = VehicleMatchingService()
    assert svc.type_codes_for_listing("Acme", "Roadster") == []


def test_type_code_for_unknown_model_returns_none(valuations) -> None:
    svc = VehicleMatchingService()
    assert svc.type_code_for("Renault", "Talisman", year=2022) is None
    assert svc.type_code_for("Acme", "Roadster") is None


def test_type_code_for_picks_a_row_when_multiple_trims_match_same_query(valuations) -> None:
    # 2022'de Clio JOY (tip 1) ve ICON (tip 2) ikisi de "Clio" sorgusuna
    # uyuyor — TSB'de aynı (marka, tip kodu, yıl) tekil olduğundan gerçek
    # bir "çoğunluk" oluşamaz; yöntem eşleşen satırlardan birini tutarlı
    # şekilde döner (hangisi olduğu değil, None DÖNMEMESİ garanti edilir).
    svc = VehicleMatchingService()
    match = svc.type_code_for("Renault", "Clio", year=2022)
    assert match is not None
    assert match.key in {(123, 1), (123, 2)}
