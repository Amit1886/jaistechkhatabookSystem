from django.contrib import admin

from .models import (
    Vendor,
    VendorCatalog,
    VendorCatalogProduct,
    VendorCatalogRollout,
    MarketplaceApp,
    VendorAppInstall,
    VendorCustomerCompany,
    VendorCustomerCompanyMember,
    VendorCustomerSegment,
    VendorMembership,
    VendorMarketingProviderConfig,
    VendorPaymentGatewayConfig,
    VendorShippingProviderConfig,
    VendorStoreSettings,
    VendorWarehouse,
    VendorShopifyConnection,
)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "subdomain", "owner", "is_active", "primary_warehouse", "created_at")
    search_fields = ("name", "subdomain", "owner__email", "owner__mobile")
    list_filter = ("is_active",)


@admin.register(VendorMembership)
class VendorMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "user", "role", "department", "is_active", "created_at")
    search_fields = ("vendor__name", "user__email", "user__mobile")
    list_filter = ("role", "is_active")


@admin.register(VendorWarehouse)
class VendorWarehouseAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "warehouse", "is_active", "created_at")
    list_filter = ("is_active",)


@admin.register(VendorPaymentGatewayConfig)
class VendorPaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "provider", "is_active", "updated_at")
    list_filter = ("provider", "is_active")
    search_fields = ("vendor__name", "vendor__subdomain")


@admin.register(VendorShippingProviderConfig)
class VendorShippingProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "provider", "is_active", "updated_at")
    list_filter = ("provider", "is_active")
    search_fields = ("vendor__name", "vendor__subdomain")


@admin.register(VendorMarketingProviderConfig)
class VendorMarketingProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "provider", "is_active", "updated_at")
    list_filter = ("provider", "is_active")
    search_fields = ("vendor__name", "vendor__subdomain")


@admin.register(VendorStoreSettings)
class VendorStoreSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "support_email", "support_phone", "currency", "timezone", "updated_at")
    search_fields = ("vendor__name", "vendor__subdomain", "support_email", "support_phone")
    readonly_fields = ("updated_at",)
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "vendor",
                    "support_email",
                    "support_phone",
                    "currency",
                    "timezone",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "pincode",
                    "country",
                )
            },
        ),
        (
            "Advanced (JSON)",
            {"fields": ("settings_json",)},
        ),
        ("Meta", {"fields": ("updated_at",)}),
    )


@admin.register(VendorCatalog)
class VendorCatalogAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "title", "is_active", "currency", "price_adjustment_direction", "price_adjustment_percent", "auto_include_new_products", "updated_at")
    list_filter = ("is_active", "currency", "auto_include_new_products", "price_adjustment_direction")
    search_fields = ("vendor__name", "vendor__subdomain", "title")


@admin.register(VendorCatalogProduct)
class VendorCatalogProductAdmin(admin.ModelAdmin):
    list_display = ("id", "catalog", "listing", "mode", "created_at")
    list_filter = ("mode",)
    search_fields = ("catalog__title", "listing__product__name", "listing__product__sku")


@admin.register(VendorCatalogRollout)
class VendorCatalogRolloutAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "catalog", "title", "status", "starts_at", "ends_at", "revert_on_end", "updated_at")
    list_filter = ("status", "revert_on_end")
    search_fields = ("vendor__name", "vendor__subdomain", "catalog__title", "title")


@admin.register(VendorCustomerCompany)
class VendorCustomerCompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "name", "gstin", "phone", "email", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("vendor__name", "vendor__subdomain", "name", "gstin", "phone", "email")


@admin.register(VendorCustomerCompanyMember)
class VendorCustomerCompanyMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "user", "role", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("company__name", "user__email", "user__mobile")


@admin.register(VendorCustomerSegment)
class VendorCustomerSegmentAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "title", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("vendor__name", "vendor__subdomain", "title")


@admin.register(MarketplaceApp)
class MarketplaceAppAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "category", "rating", "is_active", "is_builtin", "updated_at")
    list_filter = ("is_active", "is_builtin", "category")
    search_fields = ("code", "name")


@admin.register(VendorAppInstall)
class VendorAppInstallAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "app", "is_installed", "is_enabled", "updated_at")
    list_filter = ("is_installed", "is_enabled", "app__category")
    search_fields = ("vendor__name", "vendor__subdomain", "app__code", "app__name")


@admin.register(VendorShopifyConnection)
class VendorShopifyConnectionAdmin(admin.ModelAdmin):
    list_display = ("id", "vendor", "shop_domain", "is_active", "last_sync_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("vendor__name", "vendor__subdomain", "shop_domain")
