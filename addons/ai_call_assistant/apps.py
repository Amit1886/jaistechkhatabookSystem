from django.apps import AppConfig
from django.conf import settings


class AiCallAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "addons.ai_call_assistant"
    verbose_name = "Addons AI Call Assistant"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        from . import signals  # noqa: F401
