from django.contrib import admin
from .models import GSTRegistration, GSTCategory, GSTTransaction


@admin.register(GSTRegistration)
class GSTRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "gstin",
        "legal_name",
        "trade_name",
        "registration_type",
        "status",
        "effective_from",
        "effective_to",
    )
    search_fields = ("gstin", "legal_name", "trade_name")
    list_filter = ("registration_type", "status", "effective_from")


@admin.register(GSTCategory)
class GSTCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category_type",
        "hsn_code",
        "sac_code",
        "cgst_rate",
        "sgst_rate",
        "igst_rate",
        "cess_rate",
        "is_active",
    )
    search_fields = ("name", "hsn_code", "sac_code")
    list_filter = ("category_type", "is_active")


@admin.register(GSTTransaction)
class GSTTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "invoice_date",
        "transaction_type",
        "counterparty_name",
        "taxable_value",
        "total_amount",
        "registration",
    )
    search_fields = ("invoice_number", "counterparty_name", "counterparty_gstin")
    list_filter = ("transaction_type", "invoice_date", "registration")
