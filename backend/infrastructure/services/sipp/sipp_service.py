"""SIPP (Standard International Passenger Protection) sınıflandırma servisi.

Kiralama sektöründe 4 harfli kod; sınıf, kasa, vites ve yakıt/klima özelliklerini
standartlaştırır. Türkiye pazarında aynı segmentteki araçlar, segmentin en popüler
temsilcisiyle etiketlenir (ör. Hyundai i20 → "Renault Clio benzeri araç").
"""

from __future__ import annotations

from dataclasses import dataclass

# --- SIPP pozisyon sözlükleri (Türkçe) ---------------------------------
_CATEGORY_TR: dict[str, str] = {
    "M": "Mini",
    "E": "Ekonomik",
    "C": "Kompakt",
    "I": "Orta",
    "S": "Standart",
    "F": "Tam boy",
    "P": "Premium",
    "L": "Lüks",
    "X": "Özel",
}

_BODY_TR: dict[str, str] = {
    "B": "2-3 kapı",
    "C": "2/4 kapı",
    "D": "4-5 kapı hatchback/sedan",
    "W": "Station wagon",
    "V": "Minivan",
    "L": "Limuzin",
    "S": "Spor",
    "T": "Cabrio",
    "F": "SUV",
    "P": "Pickup",
    "Q": "6 teker pickup",
    "J": "Açık hava",
    "X": "Özel",
    "M": "Minibus",
    "R": "Rekreasyonel",
}

_TRANSMISSION_TR: dict[str, str] = {
    "M": "Manuel",
    "N": "Manuel (4WD)",
    "C": "Manuel (AWD)",
    "A": "Otomatik",
    "B": "Otomatik (4WD)",
    "D": "Otomatik (AWD)",
}

_FUEL_AC_TR: dict[str, str] = {
    "R": "Benzin/Dizel + Klima",
    "N": "Benzin/Dizel, klimasız",
    "D": "Dizel + Klima",
    "Q": "Dizel + Klima",
    "H": "Hibrit + Klima",
    "I": "Hibrit plug-in + Klima",
    "E": "Elektrik + Klima",
    "C": "Elektrik + Klima",
    "L": "LPG + Klima",
    "S": "LPG + Klima",
    "A": "Hidrojen + Klima",
    "B": "Hidrojen + Klima",
    "M": "Hibrit + Klima",
    "F": "Çok yakıt tipi + Klima",
    "V": "Benzin + Klima",
    "Z": "Benzin/Dizel + Klima",
    "U": "Benzin/Dizel + Klima",
    "X": "Benzin/Dizel + Klima",
}


@dataclass(frozen=True)
class SippProfile:
    """Bir aracın SIPP kodu ve Türkçe segment etiketi."""

    code: str
    segment_label: str  # örn. "Renault Clio benzeri araç"


# Marka + model → SIPP profili (seed filomuz ve yaygın TR segmentleri).
# segment_label: piyasada o segmentin popüler temsilcisi.
_MODEL_PROFILES: dict[tuple[str, str], SippProfile] = {
    # Ekonomik hatch — Clio segmenti
    ("renault", "clio"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("hyundai", "i20"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("volkswagen", "polo"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("toyota", "yaris"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("ford", "fiesta"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("renault", "symbol"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    # Mini
    ("fiat", "panda"): SippProfile("MCMR", "Fiat Panda benzeri araç"),
    ("fiat", "500"): SippProfile("MCMR", "Fiat Panda benzeri araç"),
    # Kompakt — Golf segmenti
    ("volkswagen", "golf"): SippProfile("CDMR", "Volkswagen Golf benzeri araç"),
    ("ford", "focus"): SippProfile("CDMR", "Volkswagen Golf benzeri araç"),
    ("renault", "megane"): SippProfile("CDMR", "Volkswagen Golf benzeri araç"),
    ("fiat", "egea"): SippProfile("CDMR", "Fiat Egea benzeri araç"),
    ("hyundai", "accent"): SippProfile("CDMR", "Volkswagen Golf benzeri araç"),
    # Orta sedan
    ("toyota", "corolla"): SippProfile("IDMR", "Toyota Corolla benzeri araç"),
    # Standart sedan
    ("volkswagen", "passat"): SippProfile("SDMR", "Volkswagen Passat benzeri araç"),
    # Kompakt SUV
    ("toyota", "c-hr"): SippProfile("IFMR", "Toyota C-HR benzeri araç"),
    ("hyundai", "tucson"): SippProfile("IFAR", "Hyundai Tucson benzeri araç"),
    # Ticari
    ("ford", "transit"): SippProfile("FVMR", "Ford Transit benzeri araç"),
    ("ford", "tourneo courier"): SippProfile("FVMR", "Ford Transit benzeri araç"),
    ("citroen", "berlingo"): SippProfile("FVMR", "Ford Transit benzeri araç"),
    ("peugeot", "rifter"): SippProfile("FVMR", "Ford Transit benzeri araç"),
    # Ekonomik — yaygın Enuygun modelleri
    ("opel", "corsa"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("citroen", "c3"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("kia", "picanto"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("kia", "rio"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("dacia", "sandero"): SippProfile("ECMR", "Renault Clio benzeri araç"),
    ("fiat", "egea hb"): SippProfile("CDMR", "Fiat Egea benzeri araç"),
    ("ford", "puma"): SippProfile("CFMR", "Toyota C-HR benzeri araç"),
    # Kompakt / orta sedan
    ("renault", "megane sedan"): SippProfile("IDMR", "Toyota Corolla benzeri araç"),
    ("skoda", "octavia"): SippProfile("IDMR", "Toyota Corolla benzeri araç"),
    ("skoda", "super b"): SippProfile("SDMR", "Volkswagen Passat benzeri araç"),
    # SUV
    ("peugeot", "2008"): SippProfile("CFMR", "Toyota C-HR benzeri araç"),
    ("peugeot", "3008"): SippProfile("IFAR", "Hyundai Tucson benzeri araç"),
    ("opel", "mokka"): SippProfile("CFMR", "Toyota C-HR benzeri araç"),
    ("dacia", "duster"): SippProfile("IFAR", "Hyundai Tucson benzeri araç"),
    ("dacia", "duster 4x2"): SippProfile("IFAR", "Hyundai Tucson benzeri araç"),
    ("nissan", "juke"): SippProfile("CFMR", "Toyota C-HR benzeri araç"),
    ("hyundai", "bayon"): SippProfile("CFMR", "Toyota C-HR benzeri araç"),
    ("citroen", "c5 aircross"): SippProfile("IFAR", "Hyundai Tucson benzeri araç"),
    ("fiat", "egea cross"): SippProfile("CFMR", "Toyota C-HR benzeri araç"),
    ("seat", "ateca"): SippProfile("IFAR", "Hyundai Tucson benzeri araç"),
    ("renault", "duster"): SippProfile("IFAR", "Hyundai Tucson benzeri araç"),
    ("renault", "captur"): SippProfile("CFMR", "Toyota C-HR benzeri araç"),
}

_DEFAULT_PROFILE = SippProfile("CDMR", "Volkswagen Golf benzeri araç")


def _normalize_key(brand: str, model: str) -> tuple[str, str]:
    return brand.strip().lower(), model.strip().lower()


def resolve_sipp(brand: str, model: str, sipp_code: str | None = None) -> SippProfile:
    """Marka/modele (veya kayıtlı SIPP koduna) göre profil döndürür."""
    if sipp_code and len(sipp_code.strip()) == 4:
        code = sipp_code.strip().upper()
        base = _MODEL_PROFILES.get(_normalize_key(brand, model), _DEFAULT_PROFILE)
        return SippProfile(code=code, segment_label=base.segment_label)
    return _MODEL_PROFILES.get(_normalize_key(brand, model), _DEFAULT_PROFILE)


def decode_sipp(code: str) -> dict[str, str]:
    """4 harfli SIPP kodunu Türkçe bileşenlere ayırır."""
    c = (code or "????").upper().ljust(4, "?")[:4]
    return {
        "sinif": _CATEGORY_TR.get(c[0], c[0]),
        "kasa": _BODY_TR.get(c[1], c[1]),
        "vites": _TRANSMISSION_TR.get(c[2], c[2]),
        "yakit_klima": _FUEL_AC_TR.get(c[3], c[3]),
    }


def segment_label_for(brand: str, model: str, sipp_code: str = "") -> str:
    return resolve_sipp(brand, model, sipp_code or None).segment_label


def format_marka_model_sinif(brand: str, model: str, sipp_code: str = "") -> str:
    """Örn. 'Hyundai i20 (Renault Clio benzeri araç)'."""
    label = segment_label_for(brand, model, sipp_code)
    return f"{brand} {model} ({label})"


def sipp_detay_metni(code: str) -> str:
    """SIPP kodunun insan okunur Türkçe özeti."""
    parts = decode_sipp(code)
    return (
        f"{parts['sinif']} · {parts['kasa']} · "
        f"{parts['vites']} · {parts['yakit_klima']}"
    )


# --- Enuygun listesi → SIPP türetme ------------------------------------
# Enuygun API ``sippCode`` döndürmez; marka/model + sınıf + yakıt + vites ile kod üretilir.

_ENUYGUN_CLASS_CATEGORY_BODY: dict[str, tuple[str, str]] = {
    "ekonomik": ("E", "C"),
    "orta": ("I", "D"),
    "suv": ("I", "F"),
    "üst": ("S", "D"),
    "lüks": ("P", "D"),
    "minibüs": ("F", "V"),
}

_COMPACT_SUV_HINTS = frozenset(
    {
        "2008", "juke", "bayon", "mokka", "puma", "c-hr", "chr", "cross",
        "aircross", "captur", "ecross", "egea cross",
    }
)


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _infer_category_body(brand: str, model: str, vehicle_class: str) -> tuple[str, str]:
    """Bilinmeyen model için Enuygun sınıfı ve isim ipuçlarından SIPP[0:2] üretir."""
    name = _normalize_text(model)
    cls = _normalize_text(vehicle_class)

    if cls == "suv" or any(hint in name for hint in _COMPACT_SUV_HINTS):
        if any(hint in name for hint in _COMPACT_SUV_HINTS):
            return "C", "F"
        return "I", "F"

    return _ENUYGUN_CLASS_CATEGORY_BODY.get(cls, ("C", "D"))


def _transmission_char(transmission: str) -> str:
    value = _normalize_text(transmission)
    if "otomatik" in value:
        return "A"
    if "manuel" in value:
        return "M"
    return "A"


def _fuel_char(fuel: str) -> str:
    value = _normalize_text(fuel)
    if "elektrik" in value:
        return "E"
    if "hibrit" in value:
        return "H"
    if "lpg" in value:
        return "L"
    if "dizel" in value and "benzin" not in value:
        return "D"
    return "R"


def derive_sipp_from_listing(
    brand: str,
    model: str,
    *,
    vehicle_class: str = "",
    fuel: str = "",
    transmission: str = "",
    api_sipp_code: str | None = None,
) -> str:
    """Enuygun teklifinden 4 harfli SIPP kodu türetir.

    Önce marka/model haritası, yoksa Enuygun sınıfı + gövde ipuçları kullanılır.
    Şanzıman ve yakıt API'deki Türkçe etiketlerden SIPP[2] ve SIPP[3]'e yazılır.
    """
    if api_sipp_code and len(api_sipp_code.strip()) == 4:
        return api_sipp_code.strip().upper()

    key = _normalize_key(brand, model)
    if key in _MODEL_PROFILES:
        category, body = _MODEL_PROFILES[key].code[0], _MODEL_PROFILES[key].code[1]
    else:
        category, body = _infer_category_body(brand, model, vehicle_class)

    trans = _transmission_char(transmission)
    fuel_code = _fuel_char(fuel)
    return f"{category}{body}{trans}{fuel_code}"


def sipp_segment_key(code: str) -> str:
    """SIPP segment anahtarı: sınıf + gövde (ilk 2 harf)."""
    normalized = (code or "????").upper().ljust(4, "?")[:4]
    return normalized[0:2]


def sipp_codes_match(target_code: str, listing_code: str) -> bool:
    """İki SIPP kodu aynı segmentte mi (sınıf + gövde)?"""
    return sipp_segment_key(target_code) == sipp_segment_key(listing_code)


def derive_sipp_from_reservation_vehicle(vehicle: dict) -> str:
    """Enuygun ``reservation.vehicle`` sözlüğünden SIPP üretir."""
    return derive_sipp_from_listing(
        vehicle.get("brand") or "",
        vehicle.get("name") or "",
        vehicle_class=vehicle.get("class") or "",
        fuel=vehicle.get("fuel") or "",
        transmission=vehicle.get("transmission") or "",
        api_sipp_code=vehicle.get("sippCode"),
    )