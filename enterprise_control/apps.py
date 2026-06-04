from django.apps import AppConfig


class EnterpriseControlConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enterprise_control"
    verbose_name = "Enterprise Control Center"

    def ready(self):
        from . import signals  # noqa: F401
