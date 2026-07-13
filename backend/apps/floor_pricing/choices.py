"""Fiyatlandırma TextChoices tanımları."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class ExpenseCategory(models.TextChoices):
    """Gider türleri. Yeni tür eklemek için tek satır yeterlidir."""

    # Sigorta / vergi / resmi
    KASKO = "KASKO", _("Kasko")
    TRAFIK_SIGORTASI = "TRAFIK_SIGORTASI", _("Trafik Sigortası")
    MTV = "MTV", _("MTV")
    NOTER = "NOTER", _("Noter")
    PLAKA = "PLAKA", _("Plaka")
    RUHSAT = "RUHSAT", _("Ruhsat")
    EKSPERTIZ = "EKSPERTIZ", _("Ekspertiz")
    MUAYENE = "MUAYENE", _("Muayene")
    # Bakım / mekanik
    PERIYODIK_BAKIM = "PERIYODIK_BAKIM", _("Periyodik Bakım")
    MOTOR_BAKIM = "MOTOR_BAKIM", _("Motor Bakımı")
    YAG_DEGISIMI = "YAG_DEGISIMI", _("Yağ Değişimi")
    FILTRE = "FILTRE", _("Filtre")
    LASTIK = "LASTIK", _("Lastik Değişimi")
    BALATA = "BALATA", _("Balata")
    AKU = "AKU", _("Akü")
    SANAYI = "SANAYI", _("Sanayi Masrafı")
    # Kaporta / kozmetik
    KAPORTA = "KAPORTA", _("Kaporta")
    BOYA = "BOYA", _("Boya")
    CAM = "CAM", _("Cam Değişimi")
    FAR = "FAR", _("Far")
    DETAYLI_TEMIZLIK = "DETAYLI_TEMIZLIK", _("Detaylı Temizlik")
    SERAMIK = "SERAMIK", _("Seramik Kaplama")
    PPF = "PPF", _("PPF")
    # Aksesuar / donanım
    GPS = "GPS", _("GPS Takılması")
    ARAC_TAKIP = "ARAC_TAKIP", _("Araç Takip Sistemi")
    YEDEK_ANAHTAR = "YEDEK_ANAHTAR", _("Yedek Anahtar")
    # İşletme / operasyon
    YAKIT = "YAKIT", _("Yakıt")
    ADBLUE = "ADBLUE", _("AdBlue")
    OTOPARK = "OTOPARK", _("Otopark")
    CEKICI = "CEKICI", _("Çekici")
    CEZA = "CEZA", _("Ceza")
    HGS_OGS = "HGS_OGS", _("HGS / OGS")
    YIKAMA = "YIKAMA", _("Yıkama")
    VALE = "VALE", _("Vale")
    DIGER = "DIGER", _("Diğer")


class ExpenseRecurrence(models.TextChoices):
    """Gider tekrarlama biçimi."""

    ONE_TIME = "ONE_TIME", _("Tek Seferlik")
    TIME_BASED = "TIME_BASED", _("Zaman Bazlı")  # her N ayda bir
    KM_BASED = "KM_BASED", _("Kilometre Bazlı")  # her N km'de bir
