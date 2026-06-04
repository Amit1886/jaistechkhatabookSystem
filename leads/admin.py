from django.contrib import admin

from .models import Lead, LeadActivity


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "mobile", "source", "status", "score", "assigned_to", "company", "created_at")
    list_filter = ("source", "status", "company")
    search_fields = ("name", "mobile", "email")


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "activity_type", "actor", "created_at")
    list_filter = ("activity_type",)

