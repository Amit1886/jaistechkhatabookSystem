from django.contrib import admin

from smart_khata.models import PaymentBehavior


@admin.register(PaymentBehavior)
class PaymentBehaviorAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "customer", "invoice", "due_date", "paid_date", "delay_days", "created_at")
    list_filter = ("delay_days", "due_date", "paid_date", "created_at")
    search_fields = ("customer__name", "invoice__number", "owner__username", "owner__email")
    autocomplete_fields = ("owner", "customer", "invoice")

