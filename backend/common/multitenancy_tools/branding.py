"""Kiracı marka (white-label) JSON yardımcıları."""

from __future__ import annotations

from backend.apps.companies.models import Company

DEFAULT_BRANDING: dict[str, str | None] = {
    "display_name": "RentA-Fleet PRO",
    "logo_url": None,
    "primary_color": "#3B82F6",
    "secondary_color": "#1E3A8A",
}


def company_branding_payload(company: Company | None) -> dict[str, str | None]:
    """Frontend'in tüketebileceği marka sözlüğü."""
    if company is None:
        return dict(DEFAULT_BRANDING)

    return {
        "display_name": company.display_name.strip() or company.name,
        "logo_url": company.logo_url or None,
        "primary_color": company.primary_color or DEFAULT_BRANDING["primary_color"],
        "secondary_color": company.secondary_color or DEFAULT_BRANDING["secondary_color"],
    }
