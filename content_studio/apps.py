from django.apps import AppConfig


class ContentStudioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "content_studio"

    def ready(self):
        import content_studio.signals
