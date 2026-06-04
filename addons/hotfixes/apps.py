from django.apps import AppConfig
from django.conf import settings


class HotfixesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.hotfixes"
    verbose_name = "Addons Hotfixes"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from .patches import accounts_dashboard  # noqa: F401
