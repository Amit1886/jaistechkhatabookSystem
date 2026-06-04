from django.contrib import admin
from .models import (
    Plan, BillingInvoice, Subscription, PaymentGateway,
    Commerce, Payment, PlanPermissions, FeatureRegistry, PlanFeature, SubscriptionHistory,
    UserFeatureOverride
)


# ====
# 🔐 PLAN PERMISSIONS ADMIN
# ====
@admin.register(PlanPermissions)
class PlanPermissionsAdmin(admin.ModelAdmin):
    list_display = ('plan', 'allow_dashboard', 'allow_commerce', 'allow_reports', 'allow_settings')
    list_editable = ('allow_dashboard', 'allow_commerce', 'allow_reports', 'allow_settings')
    list_filter = ('plan',)
    
    fieldsets = (
        ("📋 Plan Info", {
            "fields": ("plan",)
        }),
        ("📊 Dashboard & Reports", {
            "fields": ("allow_dashboard", "allow_reports", "allow_pdf_export", "allow_excel_export", "allow_analytics")
        }),
        ("👥 Party Management", {
            "fields": ("allow_add_party", "allow_edit_party", "allow_delete_party", "max_parties")
        }),
        ("💰 Transactions", {
            "fields": ("allow_add_transaction", "allow_edit_transaction", "allow_delete_transaction", "allow_bulk_transaction")
        }),
        ("📦 Commerce & Warehouse", {
            "fields": ("allow_commerce", "allow_warehouse", "allow_orders", "allow_inventory")
        }),
        ("📱 Communication", {
            "fields": ("allow_whatsapp", "allow_sms", "allow_email")
        }),
        ("📊 Ledger & Credit", {
            "fields": ("allow_ledger", "allow_credit_report")
        }),
        ("🔧 Admin & Settings", {
            "fields": ("allow_settings", "allow_users", "allow_api_access")
        }),
    )


# ====
# 💳 PLAN ADMIN
# ====
class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    inlines = [PlanFeatureInline]
    list_display = ('name', 'price', 'active', 'created_at')
    list_filter = ('active',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    fieldsets = (
        ("🎯 Plan Info", {
            "fields": ("name", "slug", "price", "price_monthly", "price_yearly", "discount_percent", "trial_days", "description")
        }),
        ("🔧 Settings", {
            "fields": ("active", "groups", "feature_toggle")
        }),
    )
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Auto-create permissions
        PlanPermissions.objects.get_or_create(plan=obj)


# ====
# 🧾 INVOICE ADMIN
# ====
@admin.register(BillingInvoice)
class BillingInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "user", "plan", "amount", "status", "created_at")
    search_fields = ("invoice_number", "user__username")


# ====
# 📦 SUBSCRIPTION ADMIN
# ====
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('user__username', 'plan__name')


# ====
# 🏦 PAYMENT GATEWAY ADMIN
# ====
@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'active', 'created_at')
    list_filter = ('provider', 'active')
    search_fields = ('name',)


# ====
# 🏪 COMMERCE ADMIN
# ====
@admin.register(Commerce)
class CommerceAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'user', 'category', 'contact_number', 'created_at')
    search_fields = ('business_name', 'user__username', 'contact_number')
    list_filter = ('category',)


# ====
# 💰 PAYMENT ADMIN
# ====
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'amount', 'payment_method', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'payment_method')
    search_fields = ('transaction_id', 'order__id')


@admin.register(FeatureRegistry)
class FeatureRegistryAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "group", "active", "is_advanced")
    list_filter = ("group", "active", "is_advanced")
    search_fields = ("key", "label")


@admin.register(UserFeatureOverride)
class UserFeatureOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "feature", "is_enabled", "updated_at")
    list_editable = ("is_enabled",)
    list_filter = ("feature", "is_enabled")
    search_fields = ("user__email", "user__mobile", "feature__key")


@admin.register(SubscriptionHistory)
class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "event_type", "created_at")
    list_filter = ("event_type",)


