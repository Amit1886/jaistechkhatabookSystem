from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ledger"

    def ready(self):
        # Register signals (posting engine hooks)
        from . import signals  # noqa: F401
