from django.apps import AppConfig
from django.conf import settings


class SMSCenterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sms_center"
    verbose_name = "SMS Center"

    def ready(self) -> None:
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        # Register signal handlers.
        from . import signals  # noqa: F401
