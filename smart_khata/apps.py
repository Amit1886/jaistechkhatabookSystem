from django.apps import AppConfig
from django.conf import settings


class SmartKhataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "smart_khata"
    verbose_name = "Smart Khata"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        # Register signals.
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Keep startup resilient when DB/migrations aren't ready yet.
            return
