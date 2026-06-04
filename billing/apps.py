# billing/apps.py
from django.apps import AppConfig
from django.conf import settings

class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        # signals ko yahan import karna zaroori hai taki wo register ho jayein
        import billing.signals
