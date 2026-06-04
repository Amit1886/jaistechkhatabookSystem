from django.contrib import admin

from .models import MobileCustomer
from .models import MobileInvoice
from .models import MobileInvoiceItem
from .models import MobilePayment
from .models import MobileProduct


@admin.register(MobileCustomer)
class MobileCustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "name", "phone", "updated_at")
    search_fields = ("id", "user_id", "name", "phone")
    list_filter = ("is_synced",)


@admin.register(MobileProduct)
class MobileProductAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "name", "sku", "price", "tax_percent", "updated_at")
    search_fields = ("id", "user_id", "name", "sku")
    list_filter = ("is_synced",)


@admin.register(MobileInvoice)
class MobileInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "number", "status", "total", "paid", "balance", "created_at")
    search_fields = ("id", "user_id", "number", "customer_id")
    list_filter = ("status", "is_synced")
    ordering = ("-created_at",)


@admin.register(MobileInvoiceItem)
class MobileInvoiceItemAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice_id", "product_id", "name", "qty", "unit_price", "line_total", "created_at")
    search_fields = ("id", "invoice_id", "product_id", "name")
    list_filter = ("is_synced",)
    ordering = ("-created_at",)


@admin.register(MobilePayment)
class MobilePaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice_id", "amount", "mode", "status", "paid_at")
    search_fields = ("id", "invoice_id", "reference")
    list_filter = ("mode", "status", "is_synced")
    ordering = ("-paid_at",)
