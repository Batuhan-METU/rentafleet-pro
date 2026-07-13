from django.apps import AppConfig


class CustomerProfilesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.customer_profiles"
    label = "customer_profiles"
    verbose_name = "Müşteri Profilleri"

    def ready(self) -> None:
        import backend.apps.customer_profiles.signals  # noqa: F401
