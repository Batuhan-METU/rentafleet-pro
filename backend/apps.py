from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Fleet Django app: core modules at ``backend/``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "backend"
    label = "api"
