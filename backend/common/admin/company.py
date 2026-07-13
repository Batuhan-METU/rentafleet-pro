"""Django admin şirket kapsamı — süper admin hariç yalnızca kendi şirket verisi."""

from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest


def scoped_company_id(request: HttpRequest) -> int | None:
    if request.user.is_superuser:
        return None
    return getattr(request.user, "company_id", None)


def filter_queryset_for_company(
    qs: QuerySet,
    request: HttpRequest,
    *,
    lookup: str = "company",
) -> QuerySet:
    """Süper admin tüm kayıtları görür; diğerleri yalnızca kendi şirketini."""
    company_id = scoped_company_id(request)
    if company_id is None:
        return qs
    return qs.filter(**{lookup: company_id})


class CompanyScopedModelAdmin(admin.ModelAdmin):
    """Non-superuser staff yalnızca kendi şirket kayıtlarını görür ve düzenler."""

    company_lookup: str = "company"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request)
        return filter_queryset_for_company(
            qs, request, lookup=self.company_lookup
        )
