from django.apps import AppConfig
from django.conf import settings


class APIIntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api_integrations"
    verbose_name = "API Integrations"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        # Placeholder for future signal hooks (provider credential refresh, etc.)
        return
