from django.apps import AppConfig


class VehiclesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.vehicles"
    label = "vehicles"
    verbose_name = "Araçlar"
