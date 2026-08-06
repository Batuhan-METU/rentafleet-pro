"""AI asistanı için salt-okunur sorgu tool'ları.

Her handler, ilgili view'ın ZATEN çağırdığı aynı servis fonksiyonunu/
serializer'ı kullanır — hiçbir sorgu mantığı burada yeniden yazılmaz.
Dönüş değeri düz (JSON-serileştirilebilir) bir Python veri yapısıdır; DRF
``Response`` değil, çünkü sonuç HTTP'ye değil modele geri besleniyor.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from rest_framework.exceptions import NotFound
from rest_framework.request import Request

from backend.apps.rentals.models import Rental
from backend.apps.rentals.serializers import RentalSerializer
from backend.apps.vehicle_finance.models import VehicleFinancialProfile
from backend.apps.vehicle_finance.serializers import VehicleFinancialProfileSerializer
from backend.apps.vehicles.models import Vehicle
from backend.apps.vehicles.serializers import VehicleSerializer
from backend.common.multitenancy_tools.scope import (
    get_scoped_loan,
    get_scoped_rental,
    get_scoped_vehicle,
    require_user_company,
    scoped_drivers,
    scoped_vehicles,
)
from backend.infrastructure.services.ai.tools.registry import ToolSpec, register
from backend.infrastructure.services.analytics.analytics_service import get_fleet_analytics
from backend.infrastructure.services.analytics.maintenance_service import get_maintenance_alerts
from backend.infrastructure.services.common.date_helper import resolve_rental_window
from backend.infrastructure.services.cost_calculation.rental_economics_service import (
    build_pricing_decision_payload,
    build_vehicle_yearly_summary,
    rental_days_between,
)


def _resolve_vehicle(request: Request, args: dict[str, Any]) -> Vehicle:
    vehicle_id = args.get("vehicle_id")
    if vehicle_id is not None:
        return get_scoped_vehicle(request, vehicle_id)

    plate = (args.get("plate_number") or "").strip().upper().replace(" ", "")
    if not plate:
        raise NotFound("Aracı bulmak için vehicle_id veya plate_number gerekli.")
    vehicle = scoped_vehicles(request).filter(plate_number__iexact=plate).first()
    if vehicle is None:
        raise NotFound(f"'{plate}' plakalı araç bulunamadı.")
    return vehicle


def _list_vehicles(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    qs = scoped_vehicles(request).select_related("company")
    status_filter = (args.get("status") or "").strip().upper()
    if status_filter:
        qs = qs.filter(status=status_filter)
    query = (args.get("query") or "").strip()
    if query:
        qs = qs.filter(plate_number__icontains=query) | qs.filter(brand__icontains=query) | qs.filter(
            model__icontains=query
        )
    vehicles = list(qs.order_by("plate_number")[:50])
    return {"count": len(vehicles), "vehicles": VehicleSerializer(vehicles, many=True).data}


def _get_vehicle_detail(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    vehicle = _resolve_vehicle(request, args)
    data = dict(VehicleSerializer(vehicle).data)
    try:
        profile = vehicle.financial_profile
        data["financial_profile"] = VehicleFinancialProfileSerializer(profile).data
    except VehicleFinancialProfile.DoesNotExist:
        data["financial_profile"] = None
    return data


def _driver_name_query(qs: QuerySet, query: str) -> QuerySet:
    """Ad-soyad ARAMASI: `first_name`/`last_name` ayrı sütunlar olduğu için
    "Erkinel Akar" gibi çok kelimeli bir sorgu tek bir `icontains` ile hiçbir
    alana tam uymaz. Her kelime AYRI AYRI (ad VEYA soyad'da) aranır, kelimeler
    arasında VE bağlacı kullanılır — böylece kelime sırası fark etmeksizin
    doğru sürücü bulunur.
    """
    condition = Q()
    for word in query.split():
        condition &= Q(first_name__icontains=word) | Q(last_name__icontains=word)
    return qs.filter(condition)


def _list_drivers(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    from backend.apps.customer_profiles.views import _driver_list_item

    qs = scoped_drivers(request)
    query = (args.get("query") or "").strip()
    if query:
        qs = _driver_name_query(qs, query) | qs.filter(national_id__icontains=query) | qs.filter(
            phone__icontains=query
        )
    drivers = list(qs.order_by("last_name", "first_name")[:50])
    return {"count": len(drivers), "drivers": [_driver_list_item(d) for d in drivers]}


def _get_driver_detail(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    from backend.apps.customer_profiles.views import _driver_detail_item

    driver_id = args.get("driver_id")
    qs = scoped_drivers(request)
    if driver_id is not None:
        driver = qs.filter(pk=driver_id).first()
    else:
        national_id = (args.get("national_id") or "").strip()
        query = (args.get("query") or "").strip()
        if national_id:
            driver = qs.filter(national_id=national_id).first()
        elif query:
            driver = _driver_name_query(qs, query).first()
        else:
            driver = None
    if driver is None:
        raise NotFound("Sürücü bulunamadı — driver_id, national_id veya query verin.")
    return _driver_detail_item(driver)


def _get_driver_rental_history(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    driver_id = args["driver_id"]
    driver = scoped_drivers(request).filter(pk=driver_id).first()
    if driver is None:
        raise NotFound(f"#{driver_id} numaralı sürücü bulunamadı.")
    rentals = driver.rentals.select_related("vehicle").order_by("-started_at")[:50]
    return {"driver_id": driver.pk, "rentals": RentalSerializer(rentals, many=True).data}


def _get_rental_detail(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    rental = get_scoped_rental(request, args["rental_id"])
    return dict(RentalSerializer(rental).data)


def _list_rentals(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    company = require_user_company(request)
    qs = Rental.objects.filter(company=company).select_related("driver", "vehicle")
    status_filter = (args.get("status") or "").strip().upper()
    if status_filter:
        qs = qs.filter(status=status_filter)
    rentals = list(qs.order_by("-started_at")[:50])
    return {"count": len(rentals), "rentals": RentalSerializer(rentals, many=True).data}


def _get_fleet_overview(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    company = require_user_company(request)
    analytics = get_fleet_analytics(company.pk)
    return {
        "total": analytics.total,
        "rented": analytics.rented,
        "available": analytics.available,
        "maintenance": analytics.maintenance,
        "occupancy_rate": analytics.occupancy_rate,
        "avg_score": analytics.avg_score,
        "critical_anomaly_count": analytics.critical_count,
        "lowest_drivers": analytics.lowest_drivers,
    }


def _get_maintenance_alerts(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    company = require_user_company(request)
    alerts = get_maintenance_alerts(company.pk)
    return {
        "count": len(alerts),
        "alerts": [
            {
                "plate_number": a.plate,
                "brand_model": a.brand_model,
                "status": a.status,
                "km_status": a.km_status,
                "date_status": a.date_status,
                "remaining_km": a.remaining_km,
                "remaining_days": a.remaining_days,
            }
            for a in alerts
        ],
    }


def _get_vehicle_pricing_decision(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    vehicle = _resolve_vehicle(request, args)
    window, _ = resolve_rental_window(
        pickup_date_param=args.get("pickup_date"),
        dropoff_date_param=args.get("dropoff_date"),
    )
    days = rental_days_between(window.pickup_date, window.dropoff_date)
    offered = args.get("offered_price")
    payload = build_pricing_decision_payload(
        vehicle,
        days,
        pickup_date=window.pickup_date,
        dropoff_date=window.dropoff_date,
        offered_total_price=float(offered) if offered is not None else None,
    )
    payload["rental_days"] = days
    return payload


def _get_vehicle_yearly_summary(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    vehicle = _resolve_vehicle(request, args)
    year = args.get("year")
    return build_vehicle_yearly_summary(vehicle, int(year) if year else None)


def _get_vehicle_loans(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    from backend.apps.vehicle_finance.models import LoanVehicleAllocation
    from backend.apps.vehicle_finance.serializers import VehicleLoanAllocationSerializer

    vehicle = _resolve_vehicle(request, args)
    allocations = LoanVehicleAllocation.objects.filter(vehicle=vehicle).select_related("loan")
    return {"allocations": VehicleLoanAllocationSerializer(allocations, many=True).data}


def _get_loan_detail(request: Request, args: dict[str, Any]) -> dict[str, Any]:
    from backend.apps.vehicle_finance.serializers import LoanDetailSerializer

    loan = get_scoped_loan(request, args["loan_id"])
    return dict(LoanDetailSerializer(loan).data)


_VEHICLE_LOOKUP_PARAMS = {
    "vehicle_id": {"type": "integer", "description": "Araç ID'si (biliniyorsa)."},
    "plate_number": {"type": "string", "description": "Araç plakası (ör. '34ABC123')."},
}


def _driver_lookup_params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "driver_id": {"type": "integer", "description": "Sürücü ID'si (biliniyorsa)."},
        "national_id": {"type": "string", "description": "T.C. kimlik numarası."},
        "query": {"type": "string", "description": "Ad/soyad/telefon içinde ara."},
    }
    if extra:
        base.update(extra)
    return base


register(
    ToolSpec(
        name="list_vehicles",
        description="Filodaki araçları listeler; duruma (AVAILABLE/RENTED/MAINTENANCE) veya plaka/marka/model metnine göre filtrelenebilir.",
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["AVAILABLE", "RENTED", "MAINTENANCE"]},
                "query": {"type": "string", "description": "Plaka, marka veya model içinde ara."},
            },
        },
        kind="read",
        handler=_list_vehicles,
    )
)

register(
    ToolSpec(
        name="get_vehicle_detail",
        description="Tek bir aracın tüm bilgilerini getirir: künye, durum, kilometre, finansal profil özeti.",
        parameters={"type": "object", "properties": dict(_VEHICLE_LOOKUP_PARAMS)},
        kind="read",
        handler=_get_vehicle_detail,
    )
)

register(
    ToolSpec(
        name="list_drivers",
        description="Şirketin sürücülerini listeler; ad/soyad/T.C. kimlik/telefon metnine göre filtrelenebilir.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Ad, soyad, kimlik no veya telefon içinde ara."}},
        },
        kind="read",
        handler=_list_drivers,
    )
)

register(
    ToolSpec(
        name="get_driver_detail",
        description="Tek bir sürücünün tüm bilgilerini getirir: kişisel bilgiler, risk skoru/seviyesi, kara liste durumu, profil özeti.",
        parameters={"type": "object", "properties": _driver_lookup_params()},
        kind="read",
        handler=_get_driver_detail,
    )
)

register(
    ToolSpec(
        name="get_driver_rental_history",
        description="Bir sürücünün geçmiş ve mevcut tüm kiralamalarını listeler.",
        parameters={
            "type": "object",
            "properties": {"driver_id": {"type": "integer"}},
            "required": ["driver_id"],
        },
        kind="read",
        handler=_get_driver_rental_history,
    )
)

register(
    ToolSpec(
        name="get_rental_detail",
        description="Bir kiralamanın tüm detaylarını (sürücü, araç, tarihler, tutar, durum) getirir.",
        parameters={
            "type": "object",
            "properties": {"rental_id": {"type": "integer"}},
            "required": ["rental_id"],
        },
        kind="read",
        handler=_get_rental_detail,
    )
)

register(
    ToolSpec(
        name="list_rentals",
        description="Şirketin kiralamalarını listeler (en yeniden eskiye, en fazla 50); duruma göre filtrelenebilir.",
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ACTIVE", "COMPLETED", "CANCELLED"]},
            },
        },
        kind="read",
        handler=_list_rentals,
    )
)

register(
    ToolSpec(
        name="get_fleet_overview",
        description="Filonun anlık özetini getirir: toplam/kirada/müsait/bakımdaki araç sayısı, doluluk oranı, ortalama sürücü skoru, kritik anomali sayısı.",
        parameters={"type": "object", "properties": {}},
        kind="read",
        handler=_get_fleet_overview,
    )
)

register(
    ToolSpec(
        name="get_maintenance_alerts",
        description="Bakım uyarısı olan araçların listesini getirir (kritik/uyarı seviyeleriyle).",
        parameters={"type": "object", "properties": {}},
        kind="read",
        handler=_get_maintenance_alerts,
    )
)

register(
    ToolSpec(
        name="get_vehicle_pricing_decision",
        description="Bir aracın belirli tarih aralığı için maliyet tabanlı fiyatlandırma kararını (kurtaran fiyat, kâr önizlemesi) getirir.",
        parameters={
            "type": "object",
            "properties": {
                **_VEHICLE_LOOKUP_PARAMS,
                "pickup_date": {"type": "string", "format": "date"},
                "dropoff_date": {"type": "string", "format": "date"},
                "offered_price": {"type": "number", "description": "Karşılaştırma için müdürün teklif ettiği toplam fiyat (opsiyonel)."},
            },
        },
        kind="read",
        handler=_get_vehicle_pricing_decision,
    )
)

register(
    ToolSpec(
        name="get_vehicle_yearly_summary",
        description="Bir aracın belirli bir yıldaki gelir/gider/kâr özetini getirir.",
        parameters={
            "type": "object",
            "properties": {**_VEHICLE_LOOKUP_PARAMS, "year": {"type": "integer"}},
        },
        kind="read",
        handler=_get_vehicle_yearly_summary,
    )
)

register(
    ToolSpec(
        name="get_vehicle_loans",
        description="Bir aracın kredi tahsislerini (hangi kredilerle finanse edildiğini) listeler.",
        parameters={"type": "object", "properties": dict(_VEHICLE_LOOKUP_PARAMS)},
        kind="read",
        handler=_get_vehicle_loans,
    )
)

register(
    ToolSpec(
        name="get_loan_detail",
        description="Bir kredinin tüm detaylarını getirir: taksit planı, araç tahsisleri.",
        parameters={
            "type": "object",
            "properties": {"loan_id": {"type": "integer"}},
            "required": ["loan_id"],
        },
        kind="read",
        handler=_get_loan_detail,
    )
)
