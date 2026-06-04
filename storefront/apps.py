from django.apps import AppConfig


class StorefrontConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "storefront"

    def ready(self):
        # Avoid importing heavy integrations (WhatsApp, couriers, etc.) during
        # management commands like `migrate`, where app-loading should be fast
        # and side-effect-free.
        import sys

        blocked = {
            "migrate",
            "makemigrations",
            "collectstatic",
            "shell",
            "createsuperuser",
            "loaddata",
            "dumpdata",
            "test",
        }
        if any(arg in blocked for arg in sys.argv):
            return

        from . import signals  # noqa: F401
