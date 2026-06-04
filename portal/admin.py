from django.contrib import admin

from portal.models import CartItem, PaymentLink, PortalOrder, PortalPermission, PortalUser, WelcomeMessageLog


@admin.register(PortalUser)
class PortalUserAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "party", "role", "username", "is_active", "must_change_password", "created_at")
    list_filter = ("role", "is_active", "must_change_password", "created_at")
    search_fields = ("username", "party__name", "party__mobile", "party__email")
    readonly_fields = ("created_at", "updated_at", "last_login_at", "api_token_created_at", "api_token_last_used_at")
    ordering = ("-created_at", "-id")


@admin.register(PortalPermission)
class PortalPermissionAdmin(admin.ModelAdmin):
    list_display = ("id", "portal_user", "key", "allowed", "created_at")
    list_filter = ("key", "allowed")
    search_fields = ("portal_user__username", "key")
    readonly_fields = ("created_at",)


@admin.register(PortalOrder)
class PortalOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "portal_user", "party", "status", "total_amount", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("party__name", "portal_user__username")
    readonly_fields = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "portal_user", "product", "qty", "updated_at")
    search_fields = ("portal_user__username", "product__name", "product__sku")
    ordering = ("-updated_at", "-id")


@admin.register(WelcomeMessageLog)
class WelcomeMessageLogAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "party", "portal_user", "channel", "status", "to", "created_at")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("to", "party__name", "portal_user__username")
    readonly_fields = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(PaymentLink)
class PaymentLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "invoice", "amount", "status", "provider", "created_at", "paid_at")
    list_filter = ("status", "provider", "created_at")
    search_fields = ("token", "invoice__number", "reference")
    readonly_fields = ("created_at", "paid_at")
    ordering = ("-created_at", "-id")

