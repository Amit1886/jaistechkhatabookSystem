from django.contrib import admin

from validation.models import FraudAlert


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "alert_type", "severity", "status", "reference_type", "reference_id", "created_at")
    list_filter = ("alert_type", "severity", "status", "created_at")
    search_fields = ("title", "message", "reference_type")
    readonly_fields = ("created_at",)
    ordering = ("-created_at", "-id")

