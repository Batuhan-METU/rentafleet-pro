"""Django admin registrations for relational models."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest

from backend.apps.customer_profiles.models import Driver
from backend.apps.risk_checks.models import (
    CustomerFinancialProfile,
    CustomerIdentityProfile,
    CustomerLicenseProfile,
    CustomerRentalHistoryStats,
    CustomerRiskSnapshot,
    RentalApplication,
    RentalDecisionLog,
    RuleDefinition,
    RuleSet,
    VehicleRiskTier,
)
from backend.apps.reservations.models import Rental
from backend.apps.companies.models import (
    Company,
    CustomUser,
)
from backend.apps.vehicles.models import Vehicle
from backend.common.admin.company import CompanyScopedModelAdmin, filter_queryset_for_company


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "company", "is_staff")
    list_filter = ("role", "company", "is_staff", "is_superuser")
    fieldsets = UserAdmin.fieldsets + (
        ("Fleet platform", {"fields": ("role", "company")}),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request)
        return filter_queryset_for_company(qs, request, lookup="company")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_number", "created_at")
    search_fields = ("name", "tax_number")
    ordering = ("name",)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        company_id = getattr(request.user, "company_id", None)
        if company_id:
            return qs.filter(pk=company_id)
        return qs.none()


@admin.register(Driver)
class DriverAdmin(CompanyScopedModelAdmin):
    list_display = ("full_name", "national_id", "gender", "city", "license_class", "is_blacklisted", "company")
    list_filter = ("gender", "city", "is_blacklisted", "company")
    search_fields = ("first_name", "last_name", "national_id", "phone")
    ordering = ("last_name", "first_name")


@admin.register(Rental)
class RentalAdmin(CompanyScopedModelAdmin):
    company_lookup = "driver__company"
    list_display = ("driver", "vehicle", "status", "started_at", "ended_at", "start_km")
    list_filter = ("status",)
    search_fields = ("driver__last_name", "vehicle__plate_number")
    ordering = ("-started_at",)


@admin.register(Vehicle)
class VehicleAdmin(CompanyScopedModelAdmin):
    list_display = ("plate_number", "brand", "model", "sipp_code", "production_year", "status", "company")
    list_filter = ("status", "company", "brand")
    search_fields = ("plate_number", "brand", "model")
    ordering = ("plate_number",)


class CustomerIdentityProfileInline(admin.StackedInline):
    model = CustomerIdentityProfile
    extra = 0


class CustomerLicenseProfileInline(admin.StackedInline):
    model = CustomerLicenseProfile
    extra = 0


class CustomerFinancialProfileInline(admin.StackedInline):
    model = CustomerFinancialProfile
    extra = 0


DriverAdmin.inlines = (
    CustomerIdentityProfileInline,
    CustomerLicenseProfileInline,
    CustomerFinancialProfileInline,
)


@admin.register(RentalApplication)
class RentalApplicationAdmin(CompanyScopedModelAdmin):
    list_display = ("id", "driver", "status", "risk_score", "risk_level", "deposit_amount", "company", "created_at")
    list_filter = ("status", "risk_level", "company")
    search_fields = ("driver__first_name", "driver__last_name", "driver__national_id")
    ordering = ("-created_at",)


@admin.register(RentalDecisionLog)
class RentalDecisionLogAdmin(CompanyScopedModelAdmin):
    company_lookup = "application__company"
    list_display = ("application", "step", "engine", "score", "risk_level", "approved", "created_at")
    list_filter = ("step", "engine", "approved")
    ordering = ("-created_at",)


@admin.register(RuleSet)
class RuleSetAdmin(CompanyScopedModelAdmin):
    list_display = ("name", "engine", "version", "company", "is_active")
    list_filter = ("engine", "is_active", "company")


@admin.register(RuleDefinition)
class RuleDefinitionAdmin(CompanyScopedModelAdmin):
    company_lookup = "rule_set__company"
    list_display = ("code", "rule_set", "priority", "effect", "points", "is_active")
    list_filter = ("effect", "is_active")


@admin.register(VehicleRiskTier)
class VehicleRiskTierAdmin(CompanyScopedModelAdmin):
    company_lookup = "vehicle__company"
    list_display = ("vehicle", "tier")
