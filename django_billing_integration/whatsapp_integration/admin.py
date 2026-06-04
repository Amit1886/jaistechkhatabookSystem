from __future__ import annotations

from django.contrib import admin

from whatsapp_integration.models import MessageLog, TemplateMessage, WhatsAppSession


@admin.register(WhatsAppSession)
class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "status", "last_qr_at", "last_connected_at", "updated_at")
    search_fields = ("session_id",)
    list_filter = ("status",)


@admin.register(TemplateMessage)
class TemplateMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    search_fields = ("name", "text")
    list_filter = ("is_active",)


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "direction", "phone", "message_type", "status")
    search_fields = ("phone", "message")
    list_filter = ("direction", "message_type", "status")

