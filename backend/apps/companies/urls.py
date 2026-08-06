from django.urls import path

from backend.apps.companies.views import LoginView, LogoutView, MeView
from backend.apps.companies.views_saas import CompanyBrandingView, CreateNewCompanyView
from backend.apps.companies.views_settings import CompanySettingsView

urlpatterns = [
    path("saas/companies/", CreateNewCompanyView.as_view(), name="saas-create-company"),
    path("company/branding/", CompanyBrandingView.as_view(), name="company-branding"),
    path("company/settings/", CompanySettingsView.as_view(), name="company-settings"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
]
