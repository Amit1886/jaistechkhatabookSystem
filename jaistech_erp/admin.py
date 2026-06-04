from django.contrib import admin
from django.urls import reverse

from . import models


@admin.register(models.Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "mobile", "gst_number", "is_active", "updated_at")
    search_fields = ("name", "mobile", "email", "gst_number")
    list_filter = ("is_active",)


@admin.register(models.Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "code", "store_type", "is_default", "is_active")
    search_fields = ("name", "code", "business__name")
    list_filter = ("store_type", "is_active", "is_default")


@admin.register(models.Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "api_base", "order", "is_core", "is_enabled")
    search_fields = ("key", "name", "description")
    list_filter = ("is_enabled", "is_core")


@admin.register(models.Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "module", "action")
    search_fields = ("label", "key", "module__key")
    list_filter = ("module", "action")


@admin.register(models.Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "business", "is_admin", "is_system")
    search_fields = ("name", "key", "business__name")
    list_filter = ("is_admin", "is_system")
    filter_horizontal = ("permissions",)


@admin.register(models.UserBusinessMembership)
class UserBusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "business", "role", "is_active")
    search_fields = ("user__email", "user__mobile", "business__name", "role__key")
    list_filter = ("is_active", "business", "role")
    filter_horizontal = ("stores",)


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "business", "sale_price", "stock_qty", "low_stock_qty", "is_active")
    search_fields = ("name", "sku", "barcode", "category")
    list_filter = ("business", "category", "is_active")


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "mobile", "email", "loyalty_points", "is_active")
    search_fields = ("name", "mobile", "email", "gst_number")
    list_filter = ("business", "is_active")


class InvoiceLineInline(admin.TabularInline):
    model = models.InvoiceLine
    extra = 0


@admin.register(models.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "business", "store", "customer", "channel", "status", "grand_total", "invoice_date")
    search_fields = ("invoice_number", "customer__name", "payment_method")
    list_filter = ("business", "store", "channel", "status", "payment_method")
    inlines = (InvoiceLineInline,)


@admin.register(models.Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("expense_number", "business", "store", "category", "vendor_name", "amount", "expense_date")
    search_fields = ("expense_number", "category", "vendor_name")
    list_filter = ("business", "store", "category", "payment_method")


@admin.register(models.LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "business", "account_type", "opening_balance")
    search_fields = ("code", "name")
    list_filter = ("business", "account_type")


@admin.register(models.LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("business", "account", "entry_date", "reference", "debit", "credit")
    search_fields = ("reference", "memo", "account__name")
    list_filter = ("business", "account", "entry_date")


@admin.register(models.CustomEntity)
class CustomEntityAdmin(admin.ModelAdmin):
    list_display = ("display_name", "model_key", "module", "is_enabled")
    search_fields = ("display_name", "model_key", "module__key")
    list_filter = ("is_enabled",)


@admin.register(models.CustomRecord)
class CustomRecordAdmin(admin.ModelAdmin):
    list_display = ("entity", "business", "is_deleted", "updated_at")
    search_fields = ("search_text",)
    list_filter = ("business", "entity", "is_deleted")


@admin.register(models.SyncQueue)
class SyncQueueAdmin(admin.ModelAdmin):
    list_display = ("business", "device_id", "entity", "operation", "status", "created_at", "synced_at")
    search_fields = ("device_id", "entity", "operation")
    list_filter = ("business", "status", "entity", "operation")


@admin.register(models.SystemErrorLog)
class SystemErrorLogAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "status", "endpoint", "method", "status_code", "occurrences", "last_seen_at")
    search_fields = ("title", "endpoint", "problem", "root_cause", "recommended_fix", "exception")
    list_filter = ("severity", "status", "source", "status_code")
    readonly_fields = (
        "title",
        "severity",
        "source",
        "endpoint",
        "method",
        "status_code",
        "user",
        "problem",
        "root_cause",
        "recommended_fix",
        "exception",
        "traceback",
        "request_payload",
        "occurrences",
        "created_at",
        "updated_at",
        "last_seen_at",
    )
    fieldsets = (
        ("Error Notification", {"fields": ("title", "severity", "status", "source", "endpoint", "method", "status_code", "user")}),
        ("Q&A Solution", {"fields": ("problem", "root_cause", "recommended_fix")}),
        ("Developer Details", {"fields": ("exception", "traceback", "request_payload", "occurrences", "last_seen_at")}),
    )


_original_admin_index = admin.site.index


def _jaistech_admin_index(request, extra_context=None):
    extra_context = extra_context or {}
    open_errors = models.SystemErrorLog.objects.exclude(
        status="resolved",
    ).order_by("-last_seen_at", "-created_at")
    extra_context["latest_system_errors"] = open_errors[:5]
    extra_context["system_error_count"] = open_errors.count()
    extra_context["system_error_changelist_url"] = reverse(
        "admin:jaistech_erp_systemerrorlog_changelist"
    )
    return _original_admin_index(request, extra_context=extra_context)


admin.site.index = _jaistech_admin_index
