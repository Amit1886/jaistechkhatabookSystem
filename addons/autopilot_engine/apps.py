from django.apps import AppConfig
from django.conf import settings


class AutopilotEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.autopilot_engine"
    verbose_name = "Addons Autopilot Engine"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
        from . import listeners  # noqa: F401
        from .integrations import legacy_events  # noqa: F401
