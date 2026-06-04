# commerce/apps.py
import logging

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class CommerceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "commerce"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        # Ensure signal receivers are registered (ledger posting + hybrid sync queue).
        from . import signals  # noqa: F401

        # Desktop-only: enqueue model changes into SyncQueue for cloud sync.
        try:
            from .desktop_sync import register_desktop_sync_signals  # noqa: WPS433

            register_desktop_sync_signals()
        except Exception:
            # Best-effort: never block app startup due to sync wiring.
            logger.exception("Failed to register desktop sync signals")
