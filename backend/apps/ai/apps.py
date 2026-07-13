from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.apps.ai"
    label = "ai"
    verbose_name = "AI Danışman"