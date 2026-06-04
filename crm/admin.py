from django.contrib import admin

from crm.models import CallLog, CustomerNote, CustomerProfile, FollowUp, LocalShop


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "company", "lifecycle_stage", "last_contacted_at")


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "author", "created_at")


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "agent", "direction", "duration_seconds", "created_at")


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "owner", "title", "due_at", "completed_at")


@admin.register(LocalShop)
class LocalShopAdmin(admin.ModelAdmin):
    list_display = ("id", "shop_name", "mobile", "agent", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("shop_name", "mobile")
