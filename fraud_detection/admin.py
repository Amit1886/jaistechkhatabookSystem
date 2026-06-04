from django.contrib import admin

from fraud_detection.models import FraudSignal


@admin.register(FraudSignal)
class FraudSignalAdmin(admin.ModelAdmin):
    list_display = ("id", "signal_type", "severity", "status", "user", "related_user", "detected_at")
    list_filter = ("signal_type", "severity", "status")
    search_fields = ("description",)

