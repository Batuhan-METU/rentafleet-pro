"""Öngörücü bakım servisi.

Gerçek kural: bir aracın SON bakımından itibaren 15.000 km'yi VEYA 12 ayı
doldurunca bakım şarttır — hangisi önce dolarsa o geçerlidir. Bu iki sınıra
yaklaşırken üç kademeli durum üretilir:
  * Sağlıklı   — hedefe (15.000 km / 12 ay) hâlâ ``MAINTENANCE_WARNING_
    BUFFER_KM``'den (varsayılan 2.000 km) fazla VEYA 30 günden fazla var.
  * Bakım Bekleyen — hedefe son 2.000 km İÇİNDE veya son 30 gün İÇİNDE
    (henüz aşılmamış).
  * Acil — km veya süre sınırı AŞILMIŞ.
"Son bakım", aracın ``VEHICLE_MAINTENANCE`` ("Araç Bakım") kategorili en
son ``VehicleExpense`` kaydının tarihi/km'sidir (bu, sihirbazın "Giderler
→ Operasyon" adımından girilen gerçek verilerdir — ``VEHICLE_MECHANICAL``
gibi diğer kategoriler bakım sayılmaz). Hiç bakım kaydı yoksa (yeni araç),
referans noktası filoya giriş tarihi + satın alma km'sidir.

Kilometre bilgisi (``odometer_km``) gider kaydında opsiyoneldir — girilmemişse
km boyutu ``None`` (bilinmiyor) döner, asla sahte bir 0/sağlıklı değere
düşürülmez ("Bilinmiyor ≠ Sıfır", bkz. ``cash_opportunity_service.py``);
o durumda sadece tarih boyutu değerlendirilir.

Not: ``Vehicle.current_km``'nin gerçek zamanlı/güvenilir güncellenmesi
(GPS/takip cihazı entegrasyonu) bu servisin kapsamı DIŞINDADIR — ayrı bir
iş olarak ele alınacaktır; burada ne besliyorsa güncel değer olarak okunur.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Prefetch
from django.utils import timezone

from backend.apps.vehicle_finance.choices import ExpenseCategory
from backend.apps.vehicle_finance.models import VehicleExpense, VehicleFinancialProfile
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.day_math import add_months
from backend.infrastructure.services.sipp.sipp_service import format_brand_model_segment

MAINTENANCE_DUE_KM = 15_000
MAINTENANCE_DUE_MONTHS = 12
MAINTENANCE_WARNING_BUFFER_KM = 2_000  # hedefe bu kadar km kala "yaklaşıyor" — değiştirilebilir
MAINTENANCE_WARNING_DAYS_BEFORE_DUE = 30

STATUS_HEALTHY = "HEALTHY"
STATUS_WARNING = "WARNING"
STATUS_CRITICAL = "CRITICAL"

_STATUS_RANK = {STATUS_CRITICAL: 0, STATUS_WARNING: 1, STATUS_HEALTHY: 2}


@dataclass
class MaintenanceReference:
    """Bir aracın "son bakım" referans noktası — km ve/veya tarih bilinmeyebilir."""

    date: date | None
    km: int | None


@dataclass
class MaintenanceAlert:
    """Bir aracın bakım risk değerlendirmesi (km + tarih boyutu birleşik)."""

    vehicle_id: int
    plate: str
    brand_model: str
    current_km: int
    status: str
    km_status: str | None
    date_status: str | None
    last_maintenance_date: date | None
    last_maintenance_km: int | None
    target_km: int | None
    remaining_km: int | None
    progress_pct: float | None
    target_date: date | None
    remaining_days: int | None


def _resolve_reference(vehicle: Vehicle) -> MaintenanceReference:
    """Aracın son bakım referans noktasını bulur.

    Öncelik: en son ``VEHICLE_MAINTENANCE`` kategorili gider kaydı
    (expense_date'e göre en yeni — ``vehicle.expenses`` ilişkisi
    ``get_maintenance_statuses``'ta bu kategoriye zaten filtrelenmiş
    prefetch edilir). Hiç yoksa filoya giriş tarihi + satın alma km'sine
    düşülür — yeni bir aracın "ilk bakımı" bu noktadan sayılır.
    """
    candidates = sorted(
        vehicle.expenses.all(),
        key=lambda e: (e.expense_date, e.created_at),
        reverse=True,
    )
    last = candidates[0] if candidates else None
    if last is not None:
        return MaintenanceReference(date=last.expense_date, km=last.odometer_km)

    purchase_km: int | None = None
    try:
        purchase_km = vehicle.financial_profile.purchase_km
    except VehicleFinancialProfile.DoesNotExist:
        purchase_km = None
    return MaintenanceReference(date=vehicle.fleet_entry_date, km=purchase_km)


def _km_status(remaining_km: int | None) -> str | None:
    if remaining_km is None:
        return None
    if remaining_km <= 0:
        return STATUS_CRITICAL
    if remaining_km <= MAINTENANCE_WARNING_BUFFER_KM:
        return STATUS_WARNING
    return STATUS_HEALTHY


def _date_status(remaining_days: int | None) -> str | None:
    if remaining_days is None:
        return None
    if remaining_days <= 0:
        return STATUS_CRITICAL
    if remaining_days <= MAINTENANCE_WARNING_DAYS_BEFORE_DUE:
        return STATUS_WARNING
    return STATUS_HEALTHY


def _combined_status(km_status: str | None, date_status: str | None) -> str:
    known = [s for s in (km_status, date_status) if s is not None]
    if not known:
        return STATUS_HEALTHY
    return min(known, key=lambda s: _STATUS_RANK[s])


def _evaluate(vehicle: Vehicle, today: date) -> MaintenanceAlert:
    ref = _resolve_reference(vehicle)
    current_km = vehicle.current_km or 0

    km_since_last = (current_km - ref.km) if ref.km is not None else None
    target_km = (ref.km + MAINTENANCE_DUE_KM) if ref.km is not None else None
    remaining_km = (target_km - current_km) if target_km is not None else None

    target_date = add_months(ref.date, MAINTENANCE_DUE_MONTHS) if ref.date is not None else None
    remaining_days = (target_date - today).days if target_date is not None else None

    km_status = _km_status(remaining_km)
    date_status = _date_status(remaining_days)
    status = _combined_status(km_status, date_status)

    progress_pct = None
    if ref.km is not None:
        # `km_since_last`, `ref.km is not None` olduğu dalda zaten hesaplandı
        # (yukarıya bkz.) — burada da None olamaz.
        assert km_since_last is not None
        progress_pct = round(min(100.0, max(0.0, km_since_last / MAINTENANCE_DUE_KM * 100.0)), 1)

    return MaintenanceAlert(
        vehicle_id=vehicle.pk,
        plate=vehicle.plate_number,
        brand_model=format_brand_model_segment(vehicle.brand, vehicle.model, vehicle.sipp_code or ""),
        current_km=current_km,
        status=status,
        km_status=km_status,
        date_status=date_status,
        last_maintenance_date=ref.date,
        last_maintenance_km=ref.km,
        target_km=target_km,
        remaining_km=remaining_km,
        progress_pct=progress_pct,
        target_date=target_date,
        remaining_days=remaining_days,
    )


def get_maintenance_statuses(company_id: int, as_of: date | None = None) -> list[MaintenanceAlert]:
    """Şirketin TÜM araçları için bakım durumunu üretir (sağlıklı dahil).

    En acil (CRITICAL, sonra WARNING, sonra HEALTHY) önce; eşit durumdakiler
    arasında en az kalan km (biliniyorsa) önce sıralanır.
    """
    vehicles = list(
        Vehicle.objects.filter(company_id=company_id)
        .select_related("financial_profile")
        .prefetch_related(
            Prefetch(
                "expenses",
                queryset=VehicleExpense.objects.filter(category=ExpenseCategory.VEHICLE_MAINTENANCE),
            )
        )
    )
    today = as_of or timezone.localdate()
    alerts = [_evaluate(v, today) for v in vehicles]
    alerts.sort(
        key=lambda a: (
            _STATUS_RANK[a.status],
            a.remaining_km if a.remaining_km is not None else float("inf"),
        )
    )
    return alerts


def get_maintenance_alerts(company_id: int, as_of: date | None = None) -> list[MaintenanceAlert]:
    """Geriye dönük uyumluluk: yalnızca WARNING/CRITICAL araçlar (sağlıklılar hariç)."""
    return [a for a in get_maintenance_statuses(company_id, as_of=as_of) if a.status != STATUS_HEALTHY]
