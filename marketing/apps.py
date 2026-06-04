from django.apps import AppConfig
from django.conf import settings


class MarketingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "marketing"
    verbose_name = "Marketing"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
