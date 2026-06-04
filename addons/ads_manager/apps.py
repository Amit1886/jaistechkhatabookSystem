from django.apps import AppConfig
from django.conf import settings


class AdsManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.ads_manager"
    verbose_name = "Addons Ads Manager"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
