from django.apps import AppConfig
from django.conf import settings


class GroupPlanPermissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.group_plan_permissions"
    verbose_name = "Addons Group Plan Permissions"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
