from django.apps import AppConfig
from django.conf import settings


class EcommerceEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.ecommerce_engine"
    verbose_name = "Addons Ecommerce Engine"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
