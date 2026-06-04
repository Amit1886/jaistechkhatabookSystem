from django.apps import AppConfig
from django.conf import settings


class ValidationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "validation"
    verbose_name = "Smart Alerts"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        try:
            from validation import signals  # noqa: F401
        except Exception:
            # Smart alerts must never break app boot.
            pass
