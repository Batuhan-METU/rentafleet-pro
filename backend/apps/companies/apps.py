from django.apps import AppConfig


class CompanyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.companies"
    label = "companies"
    verbose_name = "Şirketler & Kimlik"
