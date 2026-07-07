"""Django admin registrations for relational models."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from backend.models import (
    Company,
    CustomUser,
    CustomerFinancialProfile,
    CustomerIdentityProfile,
    CustomerLicenseProfile,
    CustomerRentalHistoryStats,
    CustomerRiskSnapshot,
    Driver,
    Rental,
    RentalApplication,
    RentalDecisionLog,
    RuleDefinition,
    RuleSet,
    Vehicle,
    VehicleRiskTier,
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "company", "is_staff")
    list_filter = ("role", "company", "is_staff", "is_superuser")
    fieldsets = UserAdmin.fieldsets + (
        ("Fleet platform", {"fields": ("role", "company")}),
    )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_number", "created_at")
    search_fields = ("name", "tax_number")
    ordering = ("name",)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("full_name", "national_id", "gender", "city", "license_class", "is_blacklisted", "company")
    list_filter = ("gender", "city", "is_blacklisted", "company")
    search_fields = ("first_name", "last_name", "national_id", "phone")
    ordering = ("last_name", "first_name")


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ("driver", "vehicle", "status", "started_at", "ended_at", "start_km")
    list_filter = ("status",)
    search_fields = ("driver__last_name", "vehicle__plate_number")
    ordering = ("-started_at",)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
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
class RentalApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "driver", "status", "risk_score", "risk_level", "deposit_amount", "company", "created_at")
    list_filter = ("status", "risk_level", "company")
    search_fields = ("driver__first_name", "driver__last_name", "driver__national_id")
    ordering = ("-created_at",)


@admin.register(RentalDecisionLog)
class RentalDecisionLogAdmin(admin.ModelAdmin):
    list_display = ("application", "step", "engine", "score", "risk_level", "approved", "created_at")
    list_filter = ("step", "engine", "approved")
    ordering = ("-created_at",)


@admin.register(RuleSet)
class RuleSetAdmin(admin.ModelAdmin):
    list_display = ("name", "engine", "version", "company", "is_active")
    list_filter = ("engine", "is_active", "company")


@admin.register(RuleDefinition)
class RuleDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "rule_set", "priority", "effect", "points", "is_active")
    list_filter = ("effect", "is_active")


@admin.register(VehicleRiskTier)
class VehicleRiskTierAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "tier")
