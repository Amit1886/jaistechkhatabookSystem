from django.contrib import admin

from .models import SMSLog, SMSProviderSettings, SMSTemplate


@admin.register(SMSProviderSettings)
class SMSProviderSettingsAdmin(admin.ModelAdmin):
    list_display = ("provider", "sender_id", "is_active")
    list_filter = ("provider", "is_active")
    search_fields = ("sender_id",)


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "template_type", "enabled")
    list_filter = ("template_type", "enabled")
    search_fields = ("title", "message_text")


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "mobile", "template", "status")
    list_filter = ("status", "template")
    search_fields = ("mobile", "message", "response")
    readonly_fields = ("mobile", "message", "template", "status", "response", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

