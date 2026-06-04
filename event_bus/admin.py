from django.contrib import admin

from event_bus.models import EventOutbox


@admin.register(EventOutbox)
class EventOutboxAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "event_type", "status", "attempts", "created_at", "sent_at")
    list_filter = ("status", "topic", "event_type")
    search_fields = ("id", "key", "topic", "event_type", "last_error")
    readonly_fields = ("created_at", "sent_at", "updated_at")

