from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "level", "read_at", "created_at")
    list_filter = ("level",)
    search_fields = ("title", "body")

