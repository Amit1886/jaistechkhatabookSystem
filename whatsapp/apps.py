from django.apps import AppConfig
from django.conf import settings


class WhatsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "whatsapp"
    verbose_name = "WhatsApp Automation"

    def ready(self) -> None:
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        try:
            from whatsapp import signals  # noqa: F401
        except Exception:
            # Avoid breaking app startup if optional deps are missing during migrations/tests.
            pass

        # Dev/desktop quality-of-life: auto-start the bundled Node gateway when running Django runserver.
        try:
            from whatsapp.services.gateway_autostart import ensure_gateway_running

            ensure_gateway_running()
        except Exception:
            # Never block Django startup.
            return
