from django.contrib import admin

from marketing.models import Campaign, CampaignMessage, QRCode


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "channel", "status", "company", "scheduled_at", "created_at")
    list_filter = ("channel", "status", "company")
    search_fields = ("name",)


@admin.register(CampaignMessage)
class CampaignMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "destination", "status", "created_at")
    list_filter = ("status",)


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "agent", "campaign", "scan_count", "created_at")
    list_filter = ("kind",)
    search_fields = ("target_url",)
