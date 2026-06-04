from django.contrib import admin

from superapp import models


@admin.register(models.BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "business_type", "gstin", "is_active")
    list_filter = ("business_type", "is_active")
    search_fields = ("name", "owner__email", "gstin")


@admin.register(models.SuperAppModule)
class SuperAppModuleAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "category", "is_enabled", "sort_order")
    list_filter = ("category", "is_enabled")
    search_fields = ("key", "title")


@admin.register(models.CustomerWallet)
class CustomerWalletAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "tier", "usable_balance", "reward_points", "fraud_score", "is_locked")
    list_filter = ("tier", "is_locked")
    search_fields = ("customer__email", "customer__mobile")


@admin.register(models.WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "entry_type", "bucket", "amount", "points", "channel", "source", "created_at")
    list_filter = ("entry_type", "bucket", "channel", "source")
    search_fields = ("reference", "wallet__customer__email")


@admin.register(models.RewardPoint)
class RewardPointAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "points", "reason", "reference", "expires_at", "created_at")
    list_filter = ("reason",)


@admin.register(models.CashbackRule)
class CashbackRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "min_order_amount", "cashback_percent", "max_cashback", "channel", "tier", "is_active")
    list_filter = ("channel", "tier", "is_active")


@admin.register(models.GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ("code", "issued_to", "balance", "original_amount", "expires_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "issued_to__email")


@admin.register(models.EMIPlan)
class EMIPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "principal_amount", "interest_rate", "tenure_months", "monthly_installment", "status", "next_due_date")
    list_filter = ("status", "partner_finance")


@admin.register(models.ReferralBonus)
class ReferralBonusAdmin(admin.ModelAdmin):
    list_display = ("id", "referrer", "referred", "amount", "points", "status", "reference")
    list_filter = ("status",)


@admin.register(models.TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "hsn_sac", "product_category", "gst_rate", "cess_rate", "supply_type", "is_active")
    list_filter = ("gst_rate", "supply_type", "is_active")
    search_fields = ("name", "hsn_sac", "product_category")


@admin.register(models.GSTCategory)
class GSTCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "gst_rate")
    search_fields = ("code", "name")


@admin.register(models.EInvoice)
class EInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice_number", "seller_gstin", "buyer_gstin", "status", "total_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("invoice_number", "seller_gstin", "buyer_gstin", "irn")


@admin.register(models.TaxAlert)
class TaxAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "severity", "alert_type", "message", "reference", "resolved_at", "created_at")
    list_filter = ("severity", "alert_type", "resolved_at")
    search_fields = ("message", "reference")


@admin.register(models.TaxReport)
class TaxReportAdmin(admin.ModelAdmin):
    list_display = ("id", "report_type", "period", "generated_by", "created_at")
    list_filter = ("report_type", "period")


@admin.register(models.ExpenseScan)
class ExpenseScanAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "status", "vendor_name", "gstin", "invoice_number", "amount", "duplicate_of", "created_at")
    list_filter = ("status",)
    search_fields = ("vendor_name", "gstin", "invoice_number", "owner__email")


@admin.register(models.OCRResult)
class OCRResultAdmin(admin.ModelAdmin):
    list_display = ("id", "expense_scan", "confidence", "created_at")


@admin.register(models.VendorMatch)
class VendorMatchAdmin(admin.ModelAdmin):
    list_display = ("id", "expense_scan", "vendor_name", "confidence", "created_at")
    search_fields = ("vendor_name",)


@admin.register(models.ExpenseApproval)
class ExpenseApprovalAdmin(admin.ModelAdmin):
    list_display = ("id", "expense_scan", "approver", "level", "status", "decided_at")
    list_filter = ("status", "level")


@admin.register(models.ExpenseAttachment)
class ExpenseAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "expense_scan", "label", "created_at")


@admin.register(models.RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = ("id", "business_unit", "table_number", "seats", "status", "qr_token")
    list_filter = ("status",)
    search_fields = ("table_number", "qr_token")


@admin.register(models.MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "business_unit", "name", "sort_order", "is_active")
    list_filter = ("is_active",)


@admin.register(models.MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "name", "sku", "price", "tax_rate", "prep_minutes", "is_available")
    list_filter = ("is_available",)
    search_fields = ("name", "sku")


@admin.register(models.TableOrder)
class TableOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "order_number", "table", "customer", "status", "total_amount", "payment_status", "created_at")
    list_filter = ("status", "payment_status")
    search_fields = ("order_number",)


@admin.register(models.KitchenQueue)
class KitchenQueueAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "priority", "status", "cooking_started_at", "ready_at", "assigned_to")
    list_filter = ("status", "priority")


@admin.register(models.OrderStatusLog)
class OrderStatusLogAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "previous_status", "new_status", "actor", "created_at")
    list_filter = ("new_status",)


@admin.register(models.SuperDashboardSnapshot)
class SuperDashboardSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "business_unit", "period", "sales_total", "wallet_liability", "tax_alerts", "restaurant_open_orders", "created_at")
    list_filter = ("period",)


@admin.register(models.ActivityAuditLog)
class ActivityAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "actor", "module", "action", "reference", "ip_address", "created_at")
    list_filter = ("module", "action")
    search_fields = ("reference", "actor__email")

