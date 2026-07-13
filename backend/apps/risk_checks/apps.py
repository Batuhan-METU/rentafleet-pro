from django.apps import AppConfig


class RiskChecksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.risk_checks"
    label = "risk_checks"
    verbose_name = "Risk & Onay Kontrolleri"
