from django.contrib import admin

from .models import (
    PlatformSettings,
    StoreOrder,
    StorePaymentAttempt,
    StoreSettlement,
    StoreShipment,
    StoreWebhookDelivery,
    VendorProductListing,
)


@admin.register(StoreOrder)
class StoreOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "order_number", "vendor", "customer", "status", "payment_status", "total_amount", "created_at")
    list_filter = ("status", "payment_status", "vendor")
    search_fields = ("order_number", "customer__email", "customer__mobile", "vendor__name", "vendor__subdomain")


@admin.register(StorePaymentAttempt)
class StorePaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "status", "amount", "external_ref", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("order__order_number", "external_ref")


@admin.register(StoreShipment)
class StoreShipmentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "status", "tracking_number", "external_ref", "courier_name", "updated_at")
    list_filter = ("provider", "status")
    search_fields = ("order__order_number", "tracking_number", "external_ref", "courier_name")


@admin.register(StoreSettlement)
class StoreSettlementAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "status", "vendor_amount", "commission_amount", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("order__order_number",)


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "commission_percent", "platform_user", "updated_at")


@admin.register(StoreWebhookDelivery)
class StoreWebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "vendor", "status", "dedupe_key", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("vendor__subdomain", "dedupe_key")


@admin.register(VendorProductListing)
class VendorProductListingAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "product", "is_online", "is_featured", "updated_at")
    list_filter = ("vendor", "is_online", "is_featured")
    search_fields = ("vendor__subdomain", "product__name", "product__sku")
