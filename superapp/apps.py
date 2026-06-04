from django.apps import AppConfig


class SuperAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "superapp"
    verbose_name = "Unified Enterprise Super App"

