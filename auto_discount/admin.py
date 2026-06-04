from __future__ import annotations

from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import AppSettings, Customer, Product


@admin.register(AppSettings)
class AppSettingsAdmin(SingletonModelAdmin):
    """
    Admin can:
    - enable/disable auto discount
    - set min profit %
    - edit slabs in JSON
    """

    fieldsets = (
        ("Profit Protection", {"fields": ("enable_auto_discount", "min_profit_percentage")}),
        ("B2B Slabs (JSON)", {"fields": ("b2b_slabs",)}),
        ("B2C Slabs (JSON)", {"fields": ("b2c_slabs",)}),
    )

    def save_model(self, request, obj, form, change):
        # Validate JSON before saving (raises ValidationError shown in admin).
        obj.full_clean()
        return super().save_model(request, obj, form, change)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "purchase_price", "selling_price", "stock", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "customer_type", "is_active", "updated_at")
    list_filter = ("customer_type", "is_active")
    search_fields = ("name",)

