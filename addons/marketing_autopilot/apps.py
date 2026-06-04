from django.apps import AppConfig
from django.conf import settings


class MarketingAutopilotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.marketing_autopilot"
    verbose_name = "Addons Marketing Autopilot"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
