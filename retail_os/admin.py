from django.contrib import admin

from .models import (
    Branch,
    BranchAnalytics,
    BranchInventory,
    BranchPrice,
    BranchScreenMapping,
    BranchTransfer,
    BranchUser,
    CampaignPlaylist,
    CampaignPlaylistItem,
    ComboOffer,
    DarkStoreInventory,
    DeliveryAllocation,
    DeviceAssignment,
    DeviceEvent,
    DeviceHealth,
    DeviceLog,
    DynamicPriceLog,
    FestivalCampaign,
    IoTDevice,
    LiveAnnouncement,
    MediaAsset,
    OfferCampaign,
    PackingTask,
    PricingRule,
    QuickCommerceOrder,
    RetailAuditLog,
    RetailScreen,
    RiderProfile,
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "branch_type", "city", "is_active", "is_locked", "emergency_mode")
    list_filter = ("branch_type", "is_active", "is_locked", "emergency_mode")
    search_fields = ("code", "name", "city")


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "condition_type", "adjustment_type", "adjustment_value", "priority", "is_active")
    list_filter = ("condition_type", "adjustment_type", "is_active")
    search_fields = ("name", "offer_tag")


@admin.register(OfferCampaign)
class OfferCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "starts_at", "ends_at", "discount_percent", "discount_amount")
    list_filter = ("status", "auto_apply")
    search_fields = ("name", "badge_text")
    filter_horizontal = ("branches", "products", "categories")


@admin.register(RetailScreen)
class RetailScreenAdmin(admin.ModelAdmin):
    list_display = ("device_uid", "name", "branch", "orientation", "is_online", "last_seen_at")
    list_filter = ("orientation", "is_online")
    search_fields = ("device_uid", "name")


@admin.register(IoTDevice)
class IoTDeviceAdmin(admin.ModelAdmin):
    list_display = ("device_uid", "name", "device_type", "connection_type", "branch", "is_online", "is_active")
    list_filter = ("device_type", "connection_type", "is_online", "is_active")
    search_fields = ("device_uid", "name")


@admin.register(QuickCommerceOrder)
class QuickCommerceOrderAdmin(admin.ModelAdmin):
    list_display = ("order", "branch", "status", "promised_eta_minutes", "packed_at", "delivered_at")
    list_filter = ("status", "branch")
    search_fields = ("order__order_number",)


class CampaignPlaylistItemInline(admin.TabularInline):
    model = CampaignPlaylistItem
    extra = 0


@admin.register(CampaignPlaylist)
class CampaignPlaylistAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "priority", "starts_at", "ends_at")
    list_filter = ("is_active",)
    filter_horizontal = ("screens", "branches")
    inlines = [CampaignPlaylistItemInline]


for model in (
    BranchUser,
    BranchInventory,
    BranchTransfer,
    BranchAnalytics,
    ComboOffer,
    BranchPrice,
    FestivalCampaign,
    DynamicPriceLog,
    MediaAsset,
    CampaignPlaylistItem,
    LiveAnnouncement,
    BranchScreenMapping,
    DeviceAssignment,
    DeviceHealth,
    DeviceLog,
    DeviceEvent,
    DarkStoreInventory,
    PackingTask,
    RiderProfile,
    DeliveryAllocation,
    RetailAuditLog,
):
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass

