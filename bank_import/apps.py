from django.apps import AppConfig


class BankImportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bank_import"
    verbose_name = "Bank Statement Import"

