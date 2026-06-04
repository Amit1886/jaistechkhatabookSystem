from django.apps import AppConfig
from django.conf import settings


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"
    verbose_name = "Customer & Supplier Portal"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        try:
            from portal import signals  # noqa: F401
        except Exception:
            # Portal automation must not break app boot.
            pass
