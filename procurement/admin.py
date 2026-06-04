from django.contrib import admin

from procurement.models import (
    AITrainingLog,
    InvoiceSource,
    ProductUnit,
    PurchaseDraft,
    PurchaseDraftItem,
    PurchaseInvoice,
    PurchaseItem,
    SupplierAPIConnection,
    SupplierPriceAlert,
    SupplierPriceHistory,
    SupplierProduct,
    SupplierProductAlias,
    SupplierRating,
    SupplierTemplate,
)


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "product", "price", "moq", "delivery_days", "is_active", "last_updated")
    list_filter = ("is_active", "last_updated")
    search_fields = ("supplier__name", "product__name", "product__sku", "owner__email")
    autocomplete_fields = ("owner", "supplier", "product")


@admin.register(SupplierPriceHistory)
class SupplierPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "product", "old_price", "new_price", "change_pct", "updated_at", "updated_by")
    list_filter = ("updated_at",)
    search_fields = ("supplier__name", "product__name", "product__sku", "owner__email")
    autocomplete_fields = ("owner", "supplier", "product", "updated_by")


@admin.register(SupplierRating)
class SupplierRatingAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "rated_by", "delivery_speed", "product_quality", "pricing", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("supplier__name", "rated_by__email", "owner__email")
    autocomplete_fields = ("owner", "supplier", "rated_by")


@admin.register(SupplierPriceAlert)
class SupplierPriceAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "product", "direction", "change_pct", "threshold_pct", "is_read", "created_at")
    list_filter = ("direction", "is_read", "created_at")
    search_fields = ("supplier__name", "product__name", "product__sku", "owner__email")
    autocomplete_fields = ("owner", "supplier", "product")


@admin.register(InvoiceSource)
class InvoiceSourceAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "source_type", "status", "external_id", "created_at")
    list_filter = ("source_type", "status", "created_at")
    search_fields = ("external_id", "owner__email")
    autocomplete_fields = ("owner",)


@admin.register(PurchaseDraft)
class PurchaseDraftAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "invoice_number", "invoice_date", "total_amount", "confidence", "status", "auto_approved", "created_at")
    list_filter = ("status", "auto_approved", "created_at")
    search_fields = ("invoice_number", "supplier_name", "supplier__name", "owner__email")
    autocomplete_fields = ("owner", "supplier", "source", "created_order")


@admin.register(PurchaseDraftItem)
class PurchaseDraftItemAdmin(admin.ModelAdmin):
    list_display = ("id", "draft", "line_no", "raw_name", "quantity", "unit", "rate", "amount", "matched_product", "match_confidence", "requires_review")
    list_filter = ("requires_review", "match_method")
    search_fields = ("raw_name", "matched_product__name")
    autocomplete_fields = ("draft", "matched_product")


@admin.register(SupplierTemplate)
class SupplierTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "version", "is_active", "last_used_at", "updated_at")
    list_filter = ("is_active", "updated_at")
    search_fields = ("supplier__name", "owner__email")
    autocomplete_fields = ("owner", "supplier")


@admin.register(ProductUnit)
class ProductUnitAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "product", "unit_name", "multiplier", "is_active", "updated_at")
    list_filter = ("is_active", "updated_at")
    search_fields = ("product__name", "product__sku", "unit_name", "owner__email")
    autocomplete_fields = ("owner", "product")


@admin.register(SupplierProductAlias)
class SupplierProductAliasAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "raw_name", "product", "confidence", "times_used", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("supplier__name", "raw_name", "product__name", "product__sku", "owner__email")
    autocomplete_fields = ("owner", "supplier", "product")


@admin.register(AITrainingLog)
class AITrainingLogAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "event_type", "reference_type", "reference_id", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("owner__email", "reference_type")
    autocomplete_fields = ("owner",)


@admin.register(SupplierAPIConnection)
class SupplierAPIConnectionAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "name", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "supplier__name", "owner__email", "token")
    autocomplete_fields = ("owner", "supplier")


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "supplier", "invoice_number", "invoice_date", "invoice_total", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("invoice_number", "supplier__name", "owner__email")
    autocomplete_fields = ("owner", "supplier", "source", "draft", "order")


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ("id", "purchase_invoice", "product", "raw_name", "qty", "unit", "rate", "amount", "created_at")
    list_filter = ("created_at",)
    search_fields = ("raw_name", "product__name", "product__sku")
    autocomplete_fields = ("purchase_invoice", "product")
