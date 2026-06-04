from django.apps import AppConfig


class PlatformTaxComplianceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform.tax_compliance"
    label = "platform_tax"
    verbose_name = "Platform GST & Tax Compliance"

