"""Şirket kapsamlı ORM ve ClickHouse yardımcıları."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request

from backend.apps.customer_profiles.models import Driver
from backend.apps.floor_pricing.models import (
    RentalIncome,
    VehicleExpense,
)
from backend.apps.reservations.models import Rental
from backend.apps.companies.models import (
    Company,
    CustomUser,
)
from backend.apps.vehicles.models import Vehicle


def get_user_company(request: Request) -> Company | None:
    """Oturum açmış kullanıcının şirketi."""
    user = request.user
    if isinstance(user, CustomUser) and user.company_id:
        return user.company
    return None


def require_user_company(request: Request) -> Company:
    """Kullanıcının şirketini döndürür; yoksa 403."""
    company = get_user_company(request)
    if company is None:
        raise PermissionDenied("Şirket bilgisi bulunamadı veya bu işlem için yetkiniz yok.")
    return company


def user_matches_company(request: Request) -> bool:
    """Çözümlenmiş subdomain şirketi ile kullanıcı şirketi eşleşiyor mu."""
    company = getattr(request, "company", None)
    user = request.user
    if company is None:
        return True
    if not isinstance(user, CustomUser) or not user.is_authenticated:
        return True
    if user.is_superuser:
        return True
    if not user.company_id:
        return False
    return user.company_id == company.pk


def scoped_vehicles(request: Request):
    """Kullanıcının şirketine ait araçlar; yetkisizse boş queryset."""
    company = get_user_company(request)
    if company is None:
        return Vehicle.objects.none()
    return Vehicle.objects.filter(company=company)


def scoped_drivers(request: Request):
    company = get_user_company(request)
    if company is None:
        return Driver.objects.none()
    return Driver.objects.filter(company=company)


def get_scoped_vehicle(request: Request, pk: int) -> Vehicle:
    company = get_user_company(request)
    return get_object_or_404(Vehicle, pk=pk, company=company)


def get_scoped_driver(request: Request, pk: int) -> Driver:
    company = get_user_company(request)
    return get_object_or_404(Driver, pk=pk, company=company)


def get_scoped_rental(request: Request, pk: int) -> Rental:
    company = get_user_company(request)
    return get_object_or_404(Rental, pk=pk, driver__company=company)


def get_scoped_expense(request: Request, pk: int) -> VehicleExpense:
    company = get_user_company(request)
    return get_object_or_404(VehicleExpense, pk=pk, vehicle__company=company)


def get_scoped_income(request: Request, pk: int) -> RentalIncome:
    company = get_user_company(request)
    return get_object_or_404(RentalIncome, pk=pk, vehicle__company=company)


def company_vehicle_ids(company_id: int) -> list[int]:
    """ClickHouse sorgularında ``device_id IN (...)`` için şirket araçları."""
    return list(
        Vehicle.objects.filter(company_id=company_id).values_list("id", flat=True)
    )
