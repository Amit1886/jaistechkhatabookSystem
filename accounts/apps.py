from django.apps import AppConfig
from django.conf import settings
import os
import sys


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        if getattr(settings, "LIGHTWEIGHT_DEPLOYMENT", False):
            return

        import accounts.signals

        # ❌ avoid DB work during migrate / collectstatic
        if "runserver" not in sys.argv and "gunicorn" not in sys.argv:
            return

        if os.environ.get("AUTO_CREATE_SUPERUSER", "false").lower() != "true":
            return

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()

            username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
            email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
            password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Admin@123")

            if not User.objects.filter(username=username).exists():
                User.objects.create_superuser(username, email, password)
                print("✅ Auto superuser created")

        except Exception as e:
            print("⚠️ Superuser create skipped:", e)
