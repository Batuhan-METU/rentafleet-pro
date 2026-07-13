from django.apps import AppConfig


class ReservationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.reservations"
    label = "reservations"
    verbose_name = "Rezervasyonlar"
