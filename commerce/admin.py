from django.contrib import admin
from .models import (
    Warehouse, Category, Product, Stock,
    ChatThread, ChatMessage,
    Order, OrderItem, Invoice, Payment, Notification,
    Quotation, QuotationItem,
    SyncQueue,
    SyncMapping,
    SyncedInvoice,
    SyncedObject,
    Coupon, UserCoupon, CouponUsage,
    CommerceAISettings, WhatsAppOrderInbox,
    WhatsAppSession, WhatsAppCartItem
)
from commerce.services.quotations import convert_quotation_to_order_now, transition_status


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "capacity", "created_at")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "sku", "gst_rate", "owner")
    search_fields = ("name", "sku")


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("product", "warehouse", "quantity", "updated_at")


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("party", "created_at")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sent_by", "text", "created_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "party", "status", "created_at", "owner")
    list_filter = ("status", "created_at")
    search_fields = ("invoice_number", "party__name", "party__mobile", "party__email", "order_source", "owner__email")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "qty", "price")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "order", "amount", "status", "created_at")
    search_fields = ("number", "order__id", "order__party__name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "method", "reference", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("message", "is_read", "created_at")


@admin.register(SyncQueue)
class SyncQueueAdmin(admin.ModelAdmin):
    list_display = ("model_name", "object_id", "action", "synced", "attempts", "created_at", "updated_at")
    list_filter = ("model_name", "action", "synced", "created_at")
    search_fields = ("model_name", "object_id")


@admin.register(SyncMapping)
class SyncMappingAdmin(admin.ModelAdmin):
    list_display = ("device_id", "model_name", "local_id", "cloud_id", "updated_at")
    list_filter = ("model_name", "device_id")
    search_fields = ("device_id", "model_name", "local_id", "cloud_id")


@admin.register(SyncedInvoice)
class SyncedInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "received_at", "updated_at")
    search_fields = ("number",)
    readonly_fields = ("received_at", "updated_at")


@admin.register(SyncedObject)
class SyncedObjectAdmin(admin.ModelAdmin):
    list_display = ("model_name", "local_id", "action", "device_id", "updated_at")
    list_filter = ("model_name", "action", "device_id")
    search_fields = ("model_name", "local_id", "device_id")
    readonly_fields = ("received_at", "updated_at")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "title", "code", "coupon_type",
        "discount_value", "usage_limit",
        "is_active", "valid_until"
    )
    list_filter = ("coupon_type", "is_active", "valid_from", "valid_until")
    search_fields = ("title", "code")
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserCoupon)
class UserCouponAdmin(admin.ModelAdmin):
    list_display = ("user", "coupon", "is_used", "assigned_at")
    list_filter = ("is_used", "assigned_at")
    search_fields = ("user__username", "coupon__code")


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "order", "discount_amount", "used_at")
    list_filter = ("used_at",)
    search_fields = ("coupon__code", "user__username")


@admin.register(CommerceAISettings)
class CommerceAISettingsAdmin(admin.ModelAdmin):
    list_display = (
        "fast_daily_sales",
        "medium_daily_sales",
        "slow_daily_sales",
        "safety_factor",
        "default_budget",
        "default_target_days",
        "updated_at",
    )


@admin.register(WhatsAppOrderInbox)
class WhatsAppOrderInboxAdmin(admin.ModelAdmin):
    list_display = (
        "id", "mobile_number", "customer_name",
        "status", "created_at", "order"
    )
    list_filter = ("status", "created_at")
    search_fields = ("mobile_number", "customer_name", "raw_message")


@admin.register(WhatsAppSession)
class WhatsAppSessionAdmin(admin.ModelAdmin):
    list_display = (
        "mobile_number", "owner", "party",
        "state", "selected_payment_mode",
        "last_message_at"
    )
    list_filter = ("state",)
    search_fields = ("mobile_number",)


@admin.register(WhatsAppCartItem)
class WhatsAppCartItemAdmin(admin.ModelAdmin):
    list_display = ("session", "product", "quantity", "unit_price")


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0
    fields = ("product", "qty", "rate", "discount", "tax", "total", "warehouse")
    readonly_fields = ("total",)


@admin.action(description="Approve selected quotations")
def approve_selected(modeladmin, request, queryset):
    ok = 0
    skipped = 0
    for q in queryset.all():
        try:
            transition_status(
                quotation_id=q.id,
                to_status=Quotation.Status.APPROVED,
                performed_by=request.user,
                action="approve",
                note="Approved (admin)",
            )
            ok += 1
        except Exception:
            skipped += 1
    modeladmin.message_user(request, f"Approved: {ok}, Skipped: {skipped}")


@admin.action(description="Reject selected quotations")
def reject_selected(modeladmin, request, queryset):
    ok = 0
    skipped = 0
    for q in queryset.all():
        try:
            transition_status(
                quotation_id=q.id,
                to_status=Quotation.Status.REJECTED,
                performed_by=request.user,
                action="reject",
                note="Rejected (admin)",
            )
            ok += 1
        except Exception:
            skipped += 1
    modeladmin.message_user(request, f"Rejected: {ok}, Skipped: {skipped}")


@admin.action(description="Convert selected quotations to orders")
def convert_selected(modeladmin, request, queryset):
    ok = 0
    skipped = 0
    for q in queryset.all():
        try:
            convert_quotation_to_order_now(quotation_id=q.id, performed_by=request.user)
            ok += 1
        except Exception:
            skipped += 1
    modeladmin.message_user(request, f"Converted: {ok}, Skipped: {skipped}")


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        "quotation_number",
        "party",
        "date",
        "valid_till",
        "status",
        "total_amount",
        "created_by",
        "created_at",
        "converted_order",
    )
    list_filter = ("status", "date", "party")
    search_fields = ("quotation_number", "party__name")
    inlines = [QuotationItemInline]
    actions = [approve_selected, reject_selected, convert_selected]


@admin.register(QuotationItem)
class QuotationItemAdmin(admin.ModelAdmin):
    list_display = ("quotation", "product", "qty", "rate", "discount", "tax", "total", "warehouse")
    list_filter = ("quotation__status", "quotation__date")
    search_fields = ("quotation__quotation_number", "product__name", "quotation__party__name")
