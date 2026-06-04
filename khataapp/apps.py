from django.apps import AppConfig
from django.conf import settings


class KhataappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "khataapp"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        # Central Business Engine signals
        try:
            from khataapp.core_engine.signals import handlers as _engine_handlers  # noqa: F401
        except Exception:
            # Never break startup due to optional engine wiring (e.g. during migrations).
            return
