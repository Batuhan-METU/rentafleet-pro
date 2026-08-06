"""TSB Kasko Değer Listesi bazlı araç çözümleme servisi.

Bu servis marka/model başlıklarını (filo aracı VEYA Enuygun ilanı) TSB
Kasko Değer Listesi'ndeki (``CarValuation``) satırlarla eşleştirir ve iki
farklı şey üretebilir:

* **Kasko bedeli / değer segmenti** (``valuation_for``, ``tier_for``) —
  yalnızca raporlama/görüntüleme içindir (ör. "kasko_degeri",
  "kasko_segmenti" bilgi alanları); piyasa eşleştirme KARARINA girmez.
* **TSB tip kodu** (``type_code_for``) — TSB'nin kendi ``brand_code``/
  ``type_code`` çiftidir; ``reservation_filter.py``'deki "TSB Tip Kodu
  Eşleşmesi" yöntemi filo aracı ile ilanın tip kodu BİREBİR AYNIYSA
  eşleştirir (artık bir değer-bandı/tolerans yok).

Çözümleme akışı ikisi için de ortak:
  1. İlan başlığını normalize et ("Renault Clio ve benzeri" → "RENAULT",
     "CLIO"); marka alanı boşsa marka başlığın içinden ayıklanır.
  2. Marka + model için TSB tip satırlarını bul (token bazlı, fuzzy yedekli).
  3. Yıla en yakın satırları seç (donanım farklılıkları için: kasko bedelinde
     medyan; tip kodunda TSB'de zaten tekil olduğu için ilk eşleşen satır).
     Filo aracında üretim yılı, ilanlarda en güncel yıl kullanılır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from difflib import get_close_matches
from statistics import median
from typing import NamedTuple

from backend.apps.enuygun.models import CarValuation


class _ValuationRow(NamedTuple):
    """Tek bir TSB satırı — marka eşleşmesi önbelleğinde tutulan biçim."""

    type_name_key: str
    year: int
    kasko_value: Decimal
    brand_code: int
    type_code: int
    brand_name: str
    type_name: str

# --- Değer segmentleri (yalnızca raporlama etiketi) -----------------------


@dataclass(frozen=True)
class ValuationTier:
    number: int
    label: str
    lower: Decimal
    upper: Decimal | None  # None → sınırsız (en üst segment)

    @property
    def code(self) -> str:
        return f"KASKO-T{self.number}"

    def contains(self, value: Decimal) -> bool:
        if value < self.lower:
            return False
        return self.upper is None or value < self.upper


VALUATION_TIERS: tuple[ValuationTier, ...] = (
    ValuationTier(1, "Ekonomik (0–1.2M ₺)", Decimal("0"), Decimal("1200000")),
    ValuationTier(2, "Orta (1.2M–2M ₺)", Decimal("1200000"), Decimal("2000000")),
    ValuationTier(3, "Üst (2M+ ₺)", Decimal("2000000"), None),
)


def tier_for_value(value: Decimal | float | int | None) -> ValuationTier | None:
    """Kasko bedelini ait olduğu değer segmentine (etiket) oturtur."""
    if value is None:
        return None
    amount = Decimal(str(value))
    if amount <= 0:
        return None
    for tier in VALUATION_TIERS:
        if tier.contains(amount):
            return tier
    return None


@dataclass(frozen=True)
class TsbTypeMatch:
    """TSB Kasko Değer Listesi'ndeki bir aracın kimliği — "TSB Tip Kodu
    Eşleşmesi" yöntemi iki aracı ``key`` birebir aynıysa eşleştirir."""

    brand_code: int
    type_code: int
    brand_name: str
    type_name: str

    @property
    def key(self) -> tuple[int, int]:
        return (self.brand_code, self.type_code)


# --- Metin normalizasyonu --------------------------------------------------

# "Renault Clio ve benzeri", "Fiat Egea veya benzeri", "Clio vb." gibi
# ekleri temizler; parantezli açıklamaları atar.
_SIMILARITY_SUFFIX_RE = re.compile(
    r"\s*(?:\(.*?\)|ve\s+benzeri|veya\s+benzeri|benzeri|vb\.?|or\s+similar)\s*$",
    re.IGNORECASE,
)

_TR_UPPER_MAP = str.maketrans({"i": "İ", "ı": "I"})


def _tr_upper(text: str) -> str:
    """Türkçe uyumlu büyük harf (i→İ, ı→I) + ASCII I'ya sadeleştirme."""
    return text.translate(_TR_UPPER_MAP).upper().replace("İ", "I")


def _normalize_key(text: str) -> str:
    """Karşılaştırma anahtarı: TR-upper, tekil boşluk, gereksiz noktalama yok."""
    cleaned = re.sub(r"[^\w\s.-]", " ", _tr_upper(text or ""))
    return re.sub(r"\s+", " ", cleaned).strip()


def _brand_tokens(name: str) -> list[str]:
    """Marka adını karşılaştırma tokenlarına ayırır (TOFAS-FIAT → TOFAS, FIAT)."""
    return [token for token in re.split(r"[^\w]+", _tr_upper(name)) if token]


def normalize_listing_model(raw_model: str) -> str:
    """İlan model adından "ve benzeri" tarzı ekleri ayıklar.

    >>> normalize_listing_model("Clio ve benzeri")
    'CLIO'
    """
    text = (raw_model or "").strip()
    # Ek birden fazla kez geçebilir ("Clio (veya benzeri) vb."); tekrar uygula.
    while True:
        stripped = _SIMILARITY_SUFFIX_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    return _normalize_key(text)


# --- Eşleştirme servisi ------------------------------------------------------


class VehicleMatchingService:
    """Marka/model → TSB kasko bedeli çözümleyici.

    Sorgu sonuçlarını örnek ömrü boyunca önbelleğe alır; aynı snapshot'taki
    yüzlerce ilan için tabloya tekrar tekrar gidilmez. Snapshot süzme gibi
    toplu işlerde tek örneği paylaşmak bu yüzden önemlidir.
    """

    def __init__(self) -> None:
        self._valuation_cache: dict[tuple[str, str, int | None], Decimal | None] = {}
        self._type_code_cache: dict[tuple[str, str, int | None], TsbTypeMatch | None] = {}
        self._type_codes_cache: dict[tuple[str, str, int | None], list[TsbTypeMatch]] = {}
        self._brand_rows_cache: dict[str, list[_ValuationRow]] = {}
        self._distinct_brands: list[str] | None = None

    # -- kamu API -------------------------------------------------------------

    def valuation_for(
        self, brand: str, model: str, *, year: int | None = None
    ) -> Decimal | None:
        """Marka/model (+ opsiyonel yıl) için TSB kasko bedeli (medyan).

        Marka boş gelirse başlığın içinden ayıklanır:
        ``valuation_for("", "Renault Clio ve benzeri")`` çalışır.
        """
        brand_key = _normalize_key(brand)
        model_key = normalize_listing_model(model)
        if not brand_key and model_key:
            brand_key, model_key = self._split_brand_from_title(model_key)
        if not brand_key or not model_key:
            return None

        cache_key = (brand_key, model_key, year)
        if cache_key not in self._valuation_cache:
            self._valuation_cache[cache_key] = self._resolve_valuation(
                brand_key, model_key, year
            )
        return self._valuation_cache[cache_key]

    def valuation_for_fleet_vehicle(self, vehicle) -> Decimal | None:
        """Filo aracının bugünkü değeri: güncel TSB listesinde üretim yılının
        bedeli (TSB her model yılını güncel piyasa değeriyle listeler)."""
        return self.valuation_for(
            vehicle.brand, vehicle.model, year=vehicle.production_year
        )

    def valuation_for_listing(self, brand: str, model: str) -> Decimal | None:
        """Piyasa ilanının değeri.

        İlanlarda model yılı bulunmaz; kiralık filolar güncel olduğundan en
        yeni kasko bedeli kullanılır (yıl verilmezse en güncel yıl seçilir).
        """
        return self.valuation_for(brand, model, year=None)

    def tier_for(
        self, brand: str, model: str, *, year: int | None = None
    ) -> ValuationTier | None:
        """Marka/model (+ opsiyonel yıl) için değer segmenti etiketi."""
        return tier_for_value(self.valuation_for(brand, model, year=year))

    def tier_for_fleet_vehicle(self, vehicle) -> ValuationTier | None:
        """Filo aracının değer segmenti etiketi (raporlama/görüntüleme)."""
        return tier_for_value(self.valuation_for_fleet_vehicle(vehicle))

    def type_code_for(
        self, brand: str, model: str, *, year: int | None = None
    ) -> TsbTypeMatch | None:
        """Marka/model (+ opsiyonel yıl) için TSB tip kodu kimliği.

        "TSB Tip Kodu Eşleşmesi" yönteminin temelidir — iki aracın
        ``TsbTypeMatch.key``'i BİREBİR aynıysa aynı TSB kataloğundaki
        modeldir sayılır. Marka boş gelirse başlığın içinden ayıklanır
        (``valuation_for`` ile aynı).
        """
        brand_key = _normalize_key(brand)
        model_key = normalize_listing_model(model)
        if not brand_key and model_key:
            brand_key, model_key = self._split_brand_from_title(model_key)
        if not brand_key or not model_key:
            return None

        cache_key = (brand_key, model_key, year)
        if cache_key not in self._type_code_cache:
            self._type_code_cache[cache_key] = self._resolve_type_code(
                brand_key, model_key, year
            )
        return self._type_code_cache[cache_key]

    def type_code_for_fleet_vehicle(self, vehicle) -> TsbTypeMatch | None:
        """Filo aracının TSB tip kodu (üretim yılına göre).

        Önce marka/model + DONANIM (``vehicle.package``, ör. "SEDAN 1.5 35
        TFSI 150 DYNAMIC STRONIC PI") birlikte denenir. Salt model adı
        (ör. "A3") aynı modelin Sedan/Cabrio/Sportback gibi FARKLI gövde
        tiplerini ayırt edemediği için token eşleşmesi rastgele bir
        varyantı seçiyordu (ör. bir Sedan aracımız Cabrio'ya çözülüp hiçbir
        Sedan ilanıyla eşleşmiyordu — gerçek veriyle doğrulandı). Donanım
        metni TSB'nin isimlendirmesiyle örtüşmüyorsa (sonuç bulunamazsa)
        salt model adına düşülür.
        """
        if vehicle.package:
            match = self.type_code_for(
                vehicle.brand, f"{vehicle.model} {vehicle.package}", year=vehicle.production_year
            )
            if match is not None:
                return match
        return self.type_code_for(
            vehicle.brand, vehicle.model, year=vehicle.production_year
        )

    def type_codes_for_listing(self, brand: str, model: str, *, year: int | None = None) -> list[TsbTypeMatch]:
        """Piyasa ilanının OLASI TSB tip kodu adayları.

        İki ayrı belirsizlik kaynağı var, ikisi de burada ele alınır:

        1. İlan başlığı genelde donanım/trim belirtmez (ör. "Renault Clio
           ve benzeri") — bu yüzden TEK bir tip koduna değil, sorguya uyan
           TÜM farklı donanım satırlarına (dolayısıyla tip kodlarına)
           karşılık gelebilir.
        2. TSB, AYNI fiziksel donanımı bile HER MODEL YILI için FARKLI bir
           tip koduna atar (``type_code`` yıla göre değişir — bkz.
           ``CarValuation.UniqueConstraint``). ``year`` filo aracının
           üretim yılı verilmelidir; ancak filo aracının tip kodu TEK bir
           yıldan (üretim yılından), ilan aramasının tip belirtmeyen
           metni ise farklı bir "en yakın yıl"a düşebiliyor — ikisi hep
           örtüşmeyebiliyordu (gerçek veriyle doğrulandı). Bunun için
           adaylar ``year-1``/``year``/``year+1`` ÜÇ yılın BİRLEŞİMİNDEN
           toplanır — dar bir tolerans, "aynı model" kesinliğini bozmadan
           bitişik model yılları arasındaki tip kodu kaymasını tolere eder.

        "TSB Tip Kodu Eşleşmesi", filo aracının kodu bu adaylardan
        HERHANGİ biriyse eşleşme sayar.
        """
        brand_key = _normalize_key(brand)
        model_key = normalize_listing_model(model)
        if not brand_key and model_key:
            brand_key, model_key = self._split_brand_from_title(model_key)
        if not brand_key or not model_key:
            return []

        cache_key = (brand_key, model_key, year)
        if cache_key not in self._type_codes_cache:
            self._type_codes_cache[cache_key] = self._resolve_type_codes(brand_key, model_key, year)
        return self._type_codes_cache[cache_key]

    # -- iç mantık --------------------------------------------------------------

    def _all_brand_names(self) -> list[str]:
        if self._distinct_brands is None:
            self._distinct_brands = list(
                CarValuation.objects.values_list("brand_name", flat=True).distinct()
            )
        return self._distinct_brands

    def _split_brand_from_title(self, title_key: str) -> tuple[str, str]:
        """"RENAULT CLIO" gibi tam başlıktan (marka, model) ayıklar.

        Başlık tokenlarının başındaki en uzun marka token dizisi eşleştirilir
        (ALFA ROMEO GIULIETTA → ALFA ROMEO + GIULIETTA). Marka bulunamazsa
        boş marka döner ve çözümleme başarısız sayılır.
        """
        title_tokens = title_key.split()
        best: tuple[int, str] = (0, "")
        for name in self._all_brand_names():
            tokens = _brand_tokens(name)
            if not tokens or len(tokens) > len(title_tokens):
                continue
            if title_tokens[: len(tokens)] == tokens and len(tokens) > best[0]:
                best = (len(tokens), _normalize_key(name))
        if best[0] == 0:
            return "", title_key
        return best[1], " ".join(title_tokens[best[0]:])

    def _brand_rows(self, brand_key: str) -> list[_ValuationRow]:
        """Markanın tüm TSB satırları (bu markaya aday isimler) — tek sorgu + önbellek."""
        if brand_key not in self._brand_rows_cache:
            rows = CarValuation.objects.filter(
                brand_name__in=self._brand_name_candidates(brand_key)
            ).values_list("type_name", "year", "kasko_value", "brand_code", "type_code", "brand_name")
            self._brand_rows_cache[brand_key] = [
                _ValuationRow(
                    type_name_key=_normalize_key(type_name),
                    year=year,
                    kasko_value=value,
                    brand_code=brand_code,
                    type_code=type_code,
                    brand_name=brand_name,
                    type_name=type_name,
                )
                for type_name, year, value, brand_code, type_code, brand_name in rows
            ]
        return self._brand_rows_cache[brand_key]

    def _brand_name_candidates(self, brand_key: str) -> list[str]:
        """TSB marka adları için aday listesi.

        TSB, markaları birleşik yazabilir ("TOFAS-FIAT", "MERCEDES-BENZ");
        bu yüzden tam eşleşmenin yanında ada gömülü marka tokenları da
        kabul edilir (FIAT → TOFAS-FIAT).
        """
        candidates = []
        for name in self._all_brand_names():
            name_key = _normalize_key(name)
            if (
                name_key == brand_key
                or name_key.startswith(brand_key)
                or brand_key.startswith(name_key)
                or brand_key in _brand_tokens(name)
            ):
                candidates.append(name)
        return candidates

    def _matched_rows_for_year(
        self, brand_key: str, model_key: str, year: int | None
    ) -> list[_ValuationRow] | None:
        """Marka/model'e uyan satırları, hedef yıla en yakın yıl grubuna daraltır.

        ``valuation_for`` (kasko bedeli medyanı) ve ``type_code_for`` (en sık
        geçen tip kodu) ORTAK olarak bu satırları kullanır — ikisi de aynı
        marka/model/yıl çözümlemesini paylaşır, yalnızca satırlardan
        çıkardıkları alan farklıdır.
        """
        rows = self._brand_rows(brand_key)
        if not rows:
            return None

        matched = self._match_type_rows(rows, model_key)
        if not matched:
            return None

        # Yıl gruplarından hedefe en yakın olanı seç; yıl verilmemişse en
        # güncel yıl (kiralık filolar yeni araçlardan oluşur).
        by_year: dict[int, list[_ValuationRow]] = {}
        for row in matched:
            by_year.setdefault(row.year, []).append(row)

        if year is not None and year in by_year:
            chosen_year = year
        elif year is not None:
            chosen_year = min(by_year, key=lambda y: (abs(y - year), -y))
        else:
            chosen_year = max(by_year)

        return by_year[chosen_year]

    def _resolve_valuation(
        self, brand_key: str, model_key: str, year: int | None
    ) -> Decimal | None:
        rows = self._matched_rows_for_year(brand_key, model_key, year)
        if not rows:
            return None

        # Aynı model-yılın donanım (trim) varyantları arasında medyan:
        # uç donanımlar değer kararını saptıramaz.
        return Decimal(str(median(row.kasko_value for row in rows)))

    def _resolve_type_code(
        self, brand_key: str, model_key: str, year: int | None
    ) -> TsbTypeMatch | None:
        rows = self._matched_rows_for_year(brand_key, model_key, year)
        if not rows:
            return None

        # TSB'de (brand_code, type_code, year) tekil olduğu için (bkz.
        # CarValuation.UniqueConstraint), bir yılda birden fazla FARKLI
        # trim aynı sorguya uyarsa (ör. "Clio" hem JOY hem ICON'a uyuyorsa)
        # aralarında gerçek bir sayısal çoğunluk oluşamaz — ilk eşleşen
        # satır temsilci alınır (deterministik, None dönmez).
        row = rows[0]
        return TsbTypeMatch(
            brand_code=row.brand_code,
            type_code=row.type_code,
            brand_name=row.brand_name,
            type_name=row.type_name,
        )

    def _resolve_type_codes(
        self, brand_key: str, model_key: str, year: int | None
    ) -> list[TsbTypeMatch]:
        """Hedef yılın ±1 yıl komşuluğundaki TÜM farklı tip kodları (bkz. ``type_codes_for_listing``).

        ``year=None`` iken (ör. bilgi amaçlı genel sorgu) yalnızca en
        güncel yıl kullanılır — tolerans sadece belirli bir hedef yıl
        (filo aracının üretim yılı) verildiğinde uygulanır.
        """
        years_to_check = (year - 1, year, year + 1) if year is not None else (None,)

        seen: dict[tuple[int, int], TsbTypeMatch] = {}
        for target_year in years_to_check:
            rows = self._matched_rows_for_year(brand_key, model_key, target_year)
            if not rows:
                continue
            for row in rows:
                key = (row.brand_code, row.type_code)
                if key not in seen:
                    seen[key] = TsbTypeMatch(
                        brand_code=row.brand_code,
                        type_code=row.type_code,
                        brand_name=row.brand_name,
                        type_name=row.type_name,
                    )
        return list(seen.values())

    @staticmethod
    def _match_type_rows(
        rows: list[_ValuationRow], model_key: str
    ) -> list[_ValuationRow]:
        """Model adını TSB tip adlarıyla eşler (token bazlı; fuzzy yedekli)."""
        tokens = model_key.split()
        first = tokens[0]

        def token_match(type_name: str) -> bool:
            # İlk token tip adının başında bir kelime olarak yer almalı
            # ("CLIO ..." ↔ "CLIO"), kalan tokenlar da geçmeli ("EGEA HB").
            type_tokens = type_name.split()
            if not type_tokens or type_tokens[0] != first:
                return False
            return all(token in type_name for token in tokens[1:])

        matched = [row for row in rows if token_match(row.type_name_key)]
        if matched:
            return matched

        # Fuzzy yedek: yazım farkları için tip adlarının ilk kelimesine bak
        # (ör. "C-HR" ↔ "C HR"). Eşik yüksek tutulur; yanlış model yakalamak
        # ortalamayı kirletmekten daha kötüdür.
        first_words = {row.type_name_key.split()[0] for row in rows if row.type_name_key}
        close = get_close_matches(first, first_words, n=1, cutoff=0.85)
        if not close:
            return []
        fuzzy_first = close[0]
        return [
            row
            for row in rows
            if row.type_name_key.split()
            and row.type_name_key.split()[0] == fuzzy_first
            and all(token in row.type_name_key for token in tokens[1:])
        ]
