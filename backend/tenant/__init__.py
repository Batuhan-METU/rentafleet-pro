"""Kiracı (tenant) markalama ve kapsam yardımcıları."""

from backend.tenant.branding import (
    DEFAULT_BRANDING,
    company_branding_payload,
)
from backend.tenant.scope import (
    company_vehicle_ids,
    get_scoped_driver,
    get_scoped_expense,
    get_scoped_income,
    get_scoped_rental,
    get_scoped_vehicle,
    get_user_company,
    scoped_drivers,
    scoped_vehicles,
)

__all__ = [
    "DEFAULT_BRANDING",
    "company_branding_payload",
    "company_vehicle_ids",
    "get_scoped_driver",
    "get_scoped_expense",
    "get_scoped_income",
    "get_scoped_rental",
    "get_scoped_vehicle",
    "get_user_company",
    "scoped_drivers",
    "scoped_vehicles",
]
