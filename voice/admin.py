from django.contrib import admin

from voice.models import VoiceCommand, VoiceCall


@admin.register(VoiceCommand)
class VoiceCommandAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "parsed_intent", "status", "created_at")
    list_filter = ("status", "parsed_intent", "created_at")
    search_fields = ("raw_text", "error")
    readonly_fields = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(VoiceCall)
class VoiceCallAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "agent", "status", "trigger", "provider", "created_at")
    list_filter = ("status", "trigger", "provider")
    search_fields = ("lead__name", "lead__mobile", "agent__email", "provider_call_id", "summary")
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at")
    ordering = ("-created_at", "-id")
