"""Genel gider payı — MALIYET_HESAPLAMA_METODOLOJISI §3.3.

Şirketin araca özel OLMAYAN genel giderleri (personel, kira, elektrik vb.),
filodaki TÜM araçlara fiyat-ağırlıklı olarak günlük bazda dağıtılır. Şube/
lokasyon ayrımı yapılmaz — tek bir havuz.

Not: RentA-Fleet PRO'da araç "filodan çıkış" tarihi tutulmuyor (henüz satış/
elden çıkarma akışı yok) — bu yüzden havuz, ``fleet_entry_date <= o_gün``
koşulunu sağlayan TÜM araçları kapsar (fiilen hâlâ filoda olmayanlar dahil
olabilir; bu, mevcut veri modelinin bir sınırıdır, doküman formülünün değil).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from backend.apps.companies.models import Company
from backend.apps.vehicle_finance.models import CompanyOverheadExpense
from backend.apps.vehicles.models import Vehicle
from backend.infrastructure.services.cost_calculation.rounding import TWO_PLACES


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def accrued_overhead_for_company(company: Company, as_of: date) -> dict[int, Decimal]:
    """§3.3 — filodaki tüm araçlar için tek geçişte fiyat-ağırlıklı dağıtım.

    Her ``CompanyOverheadExpense`` günü için, o gün itibarıyla filoda olan
    araçların (``fleet_entry_date <= o_gün``) fiyat toplamı havuz olarak
    alınır, her aracın payı ``kendi_fiyatı / havuz × o_günün_gideri``.
    Company-geneli TEK seferde bellekte hesaplanır (araç/gün başına ayrı
    sorgu yok).

    Hiç ``CompanyOverheadExpense`` kaydı yoksa boş sözlük döner — bu,
    "genel gider verisi henüz aktarılmamış" anlamına gelir (§1.5:
    Bilinmiyor ≠ Sıfır; çağıran taraf boş sözlüğü "veri yok" olarak
    yorumlamalıdır, 0 olarak değil).
    """
    rows = list(
        CompanyOverheadExpense.objects.filter(company=company, expense_date__lte=as_of)
        .order_by("expense_date")
        .values("expense_date", "amount")
    )
    if not rows:
        return {}

    vehicles = list(
        Vehicle.objects.filter(
            company=company,
            purchase_price__isnull=False,
            fleet_entry_date__isnull=False,
        ).only("id", "purchase_price", "fleet_entry_date")
    )
    if not vehicles:
        return {}

    totals: dict[int, Decimal] = {v.id: Decimal("0") for v in vehicles}
    for row in rows:
        expense_date = row["expense_date"]
        amount = Decimal(row["amount"])
        # `vehicles` yukarıda `purchase_price__isnull=False,
        # fleet_entry_date__isnull=False` ile filtrelendi — bu alanlar
        # runtime'da asla None değil, ama django-stubs QuerySet filtresinden
        # bunu çıkaramaz (statik tip hâlâ `X | None`).
        eligible = [v for v in vehicles if v.fleet_entry_date <= expense_date]  # type: ignore[operator]
        pool = sum((Decimal(v.purchase_price) for v in eligible), Decimal("0"))  # type: ignore[arg-type]
        if pool <= 0:
            continue
        for v in eligible:
            totals[v.id] += (Decimal(v.purchase_price) / pool) * amount  # type: ignore[arg-type]

    return {vehicle_id: _round(total) for vehicle_id, total in totals.items()}


def accrued_overhead_for_vehicle(vehicle: Vehicle, as_of: date) -> Decimal | None:
    """Tek araç için kolaylık sarmalayıcı — company-geneli batch'i çağırır.

    Şirket için hiç genel gider verisi yoksa ``None`` döner. Veri varsa
    ama bu araç hiç payına düşen bir gün bulamadıysa (ör. filoya çok yakın
    zamanda girdi) ``Decimal("0")`` döner — bu meşru bir sonuçtur, veri
    eksikliği değil.
    """
    company_totals = accrued_overhead_for_company(vehicle.company, as_of)
    if not company_totals:
        return None
    return company_totals.get(vehicle.id, Decimal("0"))


def average_daily_overhead(vehicle: Vehicle, as_of: date) -> Decimal | None:
    """§4 — ortalama yöntem: bugüne kadarki toplam / filoya girişten bugüne gün sayısı."""
    accrued = accrued_overhead_for_vehicle(vehicle, as_of)
    if accrued is None or vehicle.fleet_entry_date is None:
        return None
    days = (as_of - vehicle.fleet_entry_date).days
    if days <= 0:
        return Decimal("0")
    return _round(accrued / days)
