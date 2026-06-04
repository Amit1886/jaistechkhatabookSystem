from django.contrib import admin

from apps.platform.tax_compliance.models import (
    EWayBillRequest,
    GSTInvoice,
    GSTInvoiceLine,
    GSTParty,
    GSTReportSnapshot,
    GSTTaxSlab,
    HSNSACCode,
    PaymentQRProfile,
    TaxAuditLog,
    TaxValidationIssue,
)


class TenantAdmin(admin.ModelAdmin):
    list_filter = ("tenant", "is_active")


@admin.register(GSTTaxSlab)
class GSTTaxSlabAdmin(admin.ModelAdmin):
    list_display = ("name", "rate", "cess_rate", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(HSNSACCode)
class HSNSACCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "code_type", "description", "tax_slab", "is_goods", "is_active")
    search_fields = ("code", "description")
    list_filter = ("code_type", "is_goods", "tax_slab", "is_active")


@admin.register(GSTParty)
class GSTPartyAdmin(TenantAdmin):
    list_display = ("name", "party_type", "gstin", "pan", "state_code", "tenant", "is_active")
    search_fields = ("name", "gstin", "pan", "phone")
    list_filter = ("party_type", "state_code", "tenant", "is_active")


@admin.register(PaymentQRProfile)
class PaymentQRProfileAdmin(TenantAdmin):
    list_display = ("name", "upi_id", "bank_name", "account_number", "ifsc", "is_default", "tenant", "is_active")
    search_fields = ("name", "upi_id", "account_number", "ifsc")
    list_filter = ("is_default", "tenant", "is_active")


class GSTInvoiceLineInline(admin.TabularInline):
    model = GSTInvoiceLine
    extra = 0


@admin.register(GSTInvoice)
class GSTInvoiceAdmin(TenantAdmin):
    list_display = ("invoice_number", "invoice_date", "buyer", "status", "total_amount", "seller_gstin", "reverse_charge", "tenant")
    search_fields = ("invoice_number", "buyer__name", "buyer__gstin", "seller_gstin")
    list_filter = ("status", "invoice_type", "supply_type", "reverse_charge", "tenant", "invoice_date")
    inlines = [GSTInvoiceLineInline]


@admin.register(GSTInvoiceLine)
class GSTInvoiceLineAdmin(admin.ModelAdmin):
    list_display = ("invoice", "description", "hsn_sac", "quantity", "taxable_value", "tax_rate", "total")
    search_fields = ("invoice__invoice_number", "description", "hsn_sac__code")
    list_filter = ("tax_rate",)


@admin.register(EWayBillRequest)
class EWayBillRequestAdmin(TenantAdmin):
    list_display = ("invoice", "status", "transporter_name", "vehicle_number", "transport_mode", "distance_km", "eway_bill_no")
    search_fields = ("invoice__invoice_number", "transporter_name", "transporter_gstin", "vehicle_number", "eway_bill_no")
    list_filter = ("status", "transport_mode", "tenant")


@admin.register(TaxValidationIssue)
class TaxValidationIssueAdmin(TenantAdmin):
    list_display = ("code", "severity", "invoice", "message", "resolved_at", "tenant")
    search_fields = ("code", "message", "invoice__invoice_number")
    list_filter = ("severity", "code", "tenant", "resolved_at")


@admin.register(TaxAuditLog)
class TaxAuditLogAdmin(TenantAdmin):
    list_display = ("created_at", "action", "invoice", "actor", "tenant", "ip_address")
    search_fields = ("action", "invoice__invoice_number", "actor__email")
    list_filter = ("action", "tenant", "created_at")
    readonly_fields = tuple(field.name for field in TaxAuditLog._meta.fields)


@admin.register(GSTReportSnapshot)
class GSTReportSnapshotAdmin(TenantAdmin):
    list_display = ("report_type", "period", "tenant", "generated_by", "created_at")
    search_fields = ("period", "tenant__name")
    list_filter = ("report_type", "tenant", "period")

