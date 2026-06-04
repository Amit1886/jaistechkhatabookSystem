from django.contrib import admin

from smart_bi.models import (
    BusinessMetric,
    DuplicateInvoiceLog,
    DuplicateInvoiceSettings,
    FestivalCampaign,
    FestivalCampaignProduct, FraudAlert
)


class FestivalCampaignProductInline(admin.TabularInline):
    model = FestivalCampaignProduct
    extra = 1
    autocomplete_fields = ["product"]


@admin.register(FestivalCampaign)
class FestivalCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "start_date", "end_date", "discount_type", "discount_value", "theme")
    list_filter = ("status", "discount_type", "theme")
    search_fields = ("name", "owner__username", "owner__email")
    inlines = [FestivalCampaignProductInline]


@admin.register(DuplicateInvoiceSettings)
class DuplicateInvoiceSettingsAdmin(admin.ModelAdmin):
    list_display = ("owner", "enabled", "window_minutes", "strict_mode", "similarity_threshold", "updated_at")
    list_filter = ("enabled", "strict_mode")
    search_fields = ("owner__username", "owner__email")


@admin.register(DuplicateInvoiceLog)
class DuplicateInvoiceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "created_by", "invoice", "possible_duplicate", "similarity_score", "created_at")
    list_filter = ("created_at",)
    search_fields = ("invoice__number", "possible_duplicate__number", "owner__username", "owner__email")


@admin.register(BusinessMetric)
class BusinessMetricAdmin(admin.ModelAdmin):
    list_display = (
        "owner",
        "date",
        "health_score",
        "total_sales",
        "total_profit",
        "total_expense",
        "outstanding_due",
        "stock_value",
        "computed_at",
    )
    list_filter = ("date",)
    search_fields = ("owner__username", "owner__email")


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'party', 'alert_type', 'risk_score', 'is_resolved', 'created_at']
    list_filter = ['alert_type', 'is_resolved']
    search_fields = ['party__name', 'alert_type']