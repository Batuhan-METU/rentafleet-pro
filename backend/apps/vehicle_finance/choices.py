"""Fiyatlandırma TextChoices tanımları."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class ExpenseCategory(models.TextChoices):
    """Gider türleri — FYS'nin gerçek operasyon gideri kategori listesiyle
    birebir eşleşir (kullanıcının referans sistemden aldığı liste).

    Not (isimlendirme): üye adları (Python identifier + DB'de saklanan
    değer) İngilizce, ``_(...)`` label'ları kullanıcıya gösterilen Türkçe
    metin. ``ZF`` (Zorunlu Fenni muayene) Türkiye'ye özgü resmi kısaltma
    olduğu için değiştirilmedi (``BSMV``/``MTV`` ile aynı mantık, bkz.
    credit_interest_service).
    """

    VEHICLE_MECHANICAL = "VEHICLE_MECHANICAL", _("Araç Mekanik")
    FLEET_TYPE_CHANGE = "FLEET_TYPE_CHANGE", _("Filo Tipi Değişikliği")
    OPERATIONS_UNIT_DISPATCH = "OPERATIONS_UNIT_DISPATCH", _("Operasyon Birimi Sevk")
    VEHICLE_MAINTENANCE = "VEHICLE_MAINTENANCE", _("Araç Bakım")
    SSH_COST_REFLECTION = "SSH_COST_REFLECTION", _("SSH Masraf Yansıtma")
    SEASONAL_TIRE_CHANGE = "SEASONAL_TIRE_CHANGE", _("Yazlık/Kışlık Lastik Değişim")
    LOST_OR_BROKEN_KEY = "LOST_OR_BROKEN_KEY", _("Kayıp/Bozuk Anahtar")
    SUSPICIOUS_VEHICLE_REPORT = "SUSPICIOUS_VEHICLE_REPORT", _("Şüpheli Araç Bildirimi")
    PURCHASE = "PURCHASE", _("Satın Alma")
    BRANCH_FLEET_REBALANCING = "BRANCH_FLEET_REBALANCING", _("Şube Araç Artırma Azaltma")
    VEHICLE_DAMAGE_REPAIR = "VEHICLE_DAMAGE_REPAIR", _("Araç Hasar Onarım")
    ZF_INSPECTION = "ZF_INSPECTION", _("ZF Muayene")
    PLATE_AND_REGISTRATION = "PLATE_AND_REGISTRATION", _("Plaka Ruhsat")
    OTHER_TIRE_SERVICES = "OTHER_TIRE_SERVICES", _("Diğer Lastik İşlemleri")
    CONSULTANCY_VEHICLE_INSPECTION = "CONSULTANCY_VEHICLE_INSPECTION", _("Müşavirlik Araç Muayene")
    TIRE_DAMAGE_REPAIR = "TIRE_DAMAGE_REPAIR", _("Lastik Hasar Onarım")
    SALES_UNIT_DISPATCH = "SALES_UNIT_DISPATCH", _("Satış Birimi Sevk")
    RETURN_WASHING = "RETURN_WASHING", _("Kiralama Dönüşü Yıkama")
    RETURN_REFUELING = "RETURN_REFUELING", _("Kiralama Dönüşü Yakıt Alma")
    STANDARD_WASHING = "STANDARD_WASHING", _("Standart Yıkama")
    STAFF_VEHICLE_ASSIGNMENT = "STAFF_VEHICLE_ASSIGNMENT", _("Personel Araç Atama")
    TIRE_INSTALLATION_SET_OF_4 = "TIRE_INSTALLATION_SET_OF_4", _("Lastik Montaj (4 Lastik)")
    BULK_OPERATION = "BULK_OPERATION", _("Toplu İşlem")
    OTHER = "OTHER", _("Diğer")


class ExpenseRecurrence(models.TextChoices):
    """Gider tekrarlama biçimi."""

    ONE_TIME = "ONE_TIME", _("Tek Seferlik")
    TIME_BASED = "TIME_BASED", _("Zaman Bazlı")  # her N ayda bir
    KM_BASED = "KM_BASED", _("Kilometre Bazlı")  # her N km'de bir


class FinancingType(models.TextChoices):
    """Bir aracın satın alımının nasıl finanse edildiği."""

    CASH = "CASH", _("Nakit")
    LOAN = "LOAN", _("Kredi")
    MIXED = "MIXED", _("Karma")


class InsurancePolicyType(models.TextChoices):
    """Sigorta/kasko poliçe tipi."""

    COMPREHENSIVE = "COMPREHENSIVE", _("Kasko")
    LIABILITY = "LIABILITY", _("Trafik Sigortası")
    GREEN_CARD = "GREEN_CARD", _("Yeşil Kart")
    OTHER = "OTHER", _("Diğer")
