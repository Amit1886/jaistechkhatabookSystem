from django.apps import AppConfig


class PlatformIdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform.identity"
    label = "platform_identity"
    verbose_name = "Platform Identity & Access"
