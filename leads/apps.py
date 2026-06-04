from django.apps import AppConfig
from django.conf import settings


class LeadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "leads"
    verbose_name = "Leads"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
