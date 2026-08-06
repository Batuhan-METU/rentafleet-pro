"""SIPP (Standard International Passenger Protection) sınıflandırma servisi.

Kiralama sektöründe 4 harfli kod; sınıf, kasa, vites ve yakıt/klima özelliklerini
standartlaştırır. Türkiye pazarında aynı segmentteki araçlar, segmentin en popüler
temsilcisiyle etiketlenir (ör. Hyundai i20 → "Renault Clio benzeri araç").
"""

from __future__ import annotations

import re
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


# Enuygun ilan başlıkları "Renault Clio ve benzeri" gibi ekler taşır; bu
# ek temizlenmeden _MODEL_PROFILES'taki temiz ("renault","clio") anahtarı
# HİÇBİR ZAMAN eşleşmez (aynı ek, vehicle_matching_service.py'de de ayrıca
# temizlenir — modüller birbirine bağımlı olmasın diye burada küçük bir
# tekrar tercih edildi).
_LISTING_SUFFIX_RE = re.compile(
    r"\s*(?:\(.*?\)|ve\s+benzeri|veya\s+benzeri|benzeri|vb\.?|or\s+similar)\s*$",
    re.IGNORECASE,
)


def _strip_listing_suffix(model: str) -> str:
    text = (model or "").strip()
    while True:
        stripped = _LISTING_SUFFIX_RE.sub("", text).strip()
        if stripped == text:
            return text
        text = stripped


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
    """4 harfli SIPP kodunu Türkçe bileşenlere ayırır.

    Not (isimlendirme): dönüş dict'inin key'leri (``sinif``/``kasa``/
    ``vites``/``yakit_klima``) BİLİNÇLİ OLARAK Türkçe bırakılmıştır —
    ``apps/vehicles/serializers.py``'de ``sipp_ozellikler`` alanının
    değeri olarak DOĞRUDAN API yanıtına gidiyor (Faz 3 kapsamı).
    """
    c = (code or "????").upper().ljust(4, "?")[:4]
    return {
        "sinif": _CATEGORY_TR.get(c[0], c[0]),
        "kasa": _BODY_TR.get(c[1], c[1]),
        "vites": _TRANSMISSION_TR.get(c[2], c[2]),
        "yakit_klima": _FUEL_AC_TR.get(c[3], c[3]),
    }


def segment_label_for(brand: str, model: str, sipp_code: str = "") -> str:
    return resolve_sipp(brand, model, sipp_code or None).segment_label


def format_brand_model_segment(brand: str, model: str, sipp_code: str = "") -> str:
    """Örn. 'Hyundai i20 (Renault Clio benzeri araç)'."""
    label = segment_label_for(brand, model, sipp_code)
    return f"{brand} {model} ({label})"


def sipp_detail_text(code: str) -> str:
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


# Marka tek başına sınıfı (SIPP[0]) belirlemeye yeter — hem filo aracı hem
# Enuygun ilanı için: `class`/`vehicle_class` ipucu boş/tanınmayan geldiğinde
# (özellikle premium markalarda sık) jenerik "C" (Kompakt) varsayılanına
# düşüp örn. bir BMW 520i'yi ekonomi sınıfı bir araçla aynı sepete
# koymasın diye.
_PREMIUM_BRANDS_FOR_SIPP = frozenset(
    {"mercedes", "bmw", "audi", "tesla", "volvo", "lexus", "porsche"}
)


def _infer_category_body(brand: str, model: str, vehicle_class: str) -> tuple[str, str]:
    """Bilinmeyen model için marka + Enuygun sınıfı + isim ipuçlarından SIPP[0:2] üretir."""
    name = _normalize_text(model)
    cls = _normalize_text(vehicle_class)

    if cls == "suv" or any(hint in name for hint in _COMPACT_SUV_HINTS):
        if any(hint in name for hint in _COMPACT_SUV_HINTS):
            return "C", "F"
        return "I", "F"

    if _normalize_text(brand) in _PREMIUM_BRANDS_FOR_SIPP:
        return "P", "D"

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
) -> str:
    """Enuygun teklifinden 4 harfli SIPP kodu türetir.

    Enuygun'un kendi gönderdiği ``sippCode`` KASITLI OLARAK kullanılmaz —
    tedarikçilerin girdiği bu kod güvenilmez (bkz. vehicle_matching_service.py
    docstring'i). Kod her zaman gerçek özniteliklerden türetilir: önce
    marka/model haritası, yoksa Enuygun sınıfı + gövde ipuçları; şanzıman
    ve yakıt API'deki Türkçe etiketlerden SIPP[2] ve SIPP[3]'e yazılır.
    """
    key = _normalize_key(brand, _strip_listing_suffix(model))
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
    )


# --- Filo aracı → SIPP türetme -----------------------------------------
# vehicle.sipp_code (Ziraat Excel'inden) KASITLI OLARAK kullanılmaz —
# filo yöneticileri bu kodu fiyatlandırma amacıyla serbestçe giriyor,
# aracın gerçek fiziksel sınıfını yansıtmıyor. Uluslararası kod, tıpkı
# Enuygun ilanlarında olduğu gibi, gerçek marka/model + vites + yakıttan
# türetilir. `resolve_sipp()` DEĞİŞMEDİ — aracın "kendi" (Ziraat) SIPP
# kodunu göstermeye devam eden tüm ekranlar (Araçlar sayfası, dışa
# aktarım, uygun-araçlar listesi) onu kullanmaya devam eder.


def derive_international_sipp_for_vehicle(vehicle) -> str:
    """Filo aracı için uluslararası SIPP kodu — eşleştirmede kullanılır.

    ``vehicle.sipp_code``'a hiç bakmaz. Sınıf/kasa marka+model tablosundan
    (veya premium marka/isim ipuçlarından, bkz. ``_infer_category_body``);
    vites+yakıt aracın kendi ``transmission``/``fuel_type`` alanlarından
    türetilir.
    """
    key = _normalize_key(vehicle.brand, vehicle.model)
    if key in _MODEL_PROFILES:
        category, body = _MODEL_PROFILES[key].code[0], _MODEL_PROFILES[key].code[1]
    else:
        category, body = _infer_category_body(vehicle.brand, vehicle.model, "")

    trans = _transmission_char(vehicle.get_transmission_display())
    fuel_code = _fuel_char(vehicle.get_fuel_type_display())
    return f"{category}{body}{trans}{fuel_code}"