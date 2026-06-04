from django.apps import AppConfig
from django.conf import settings


class PlanFeatureSyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.plan_feature_sync"
    verbose_name = "Addon: Plan -> Feature Sync"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        # Register signals (kept in addon to avoid touching billing/core apps).
        from . import signals  # noqa: F401
