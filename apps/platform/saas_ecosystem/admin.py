from django.contrib import admin

from apps.platform.saas_ecosystem.models import (
    DeliveryAssignment,
    EcosystemPartner,
    ForecastModel,
    FranchiseAgreement,
    PaymentRetry,
    RoutePlan,
    SaaSInvoice,
    SaaSPlan,
    SalesmanTracking,
    TenantDomain,
    TenantSubscription,
    UsageMetric,
    UsageRecord,
    VanSalesSession,
    WarehouseRoute,
    WhiteLabelProfile,
)


class TenantAdmin(admin.ModelAdmin):
    list_filter = ("tenant", "is_active")


@admin.register(WhiteLabelProfile)
class WhiteLabelProfileAdmin(TenantAdmin):
    list_display = ("brand_name", "tenant", "primary_color", "invoice_template", "is_active")
    search_fields = ("brand_name", "tenant__name")


@admin.register(TenantDomain)
class TenantDomainAdmin(TenantAdmin):
    list_display = ("domain", "tenant", "is_primary", "ssl_status", "verified_at", "is_active")
    search_fields = ("domain", "tenant__name")
    list_filter = ("ssl_status", "is_primary", "tenant", "is_active")


@admin.register(SaaSPlan)
class SaaSPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "interval", "base_price", "currency", "trial_days", "is_active")
    search_fields = ("name", "key")
    list_filter = ("interval", "is_active")


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(TenantAdmin):
    list_display = ("tenant", "plan", "status", "current_period_end", "auto_renew", "is_active")
    list_filter = ("status", "plan", "tenant", "is_active")


@admin.register(UsageMetric)
class UsageMetricAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "unit", "billable", "unit_price")
    search_fields = ("key", "name")
    list_filter = ("billable",)


@admin.register(UsageRecord)
class UsageRecordAdmin(TenantAdmin):
    list_display = ("tenant", "metric", "quantity", "period", "source_type", "source_id")
    list_filter = ("metric", "period", "tenant")


@admin.register(SaaSInvoice)
class SaaSInvoiceAdmin(TenantAdmin):
    list_display = ("invoice_number", "tenant", "status", "subtotal", "tax_amount", "total", "due_at")
    search_fields = ("invoice_number", "tenant__name")
    list_filter = ("status", "tenant", "due_at")


@admin.register(PaymentRetry)
class PaymentRetryAdmin(TenantAdmin):
    list_display = ("invoice", "tenant", "attempt_no", "status", "scheduled_at", "attempted_at")
    list_filter = ("status", "tenant", "scheduled_at")


@admin.register(EcosystemPartner)
class EcosystemPartnerAdmin(TenantAdmin):
    list_display = ("code", "name", "partner_type", "parent", "tenant", "credit_limit", "is_active")
    search_fields = ("code", "name", "tenant__name")
    list_filter = ("partner_type", "tenant", "is_active")


@admin.register(FranchiseAgreement)
class FranchiseAgreementAdmin(TenantAdmin):
    list_display = ("partner", "tenant", "starts_at", "ends_at", "royalty_percent", "is_active")
    list_filter = ("tenant", "is_active")


@admin.register(RoutePlan)
class RoutePlanAdmin(TenantAdmin):
    list_display = ("code", "name", "owner", "salesman", "tenant", "is_active")
    search_fields = ("code", "name", "salesman__email")


@admin.register(SalesmanTracking)
class SalesmanTrackingAdmin(TenantAdmin):
    list_display = ("salesman", "route", "tenant", "latitude", "longitude", "recorded_at")
    list_filter = ("tenant", "recorded_at")


@admin.register(VanSalesSession)
class VanSalesSessionAdmin(TenantAdmin):
    list_display = ("salesman", "route", "vehicle_no", "status", "cash_collected", "started_at", "ended_at")
    list_filter = ("status", "tenant", "started_at")


@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(TenantAdmin):
    list_display = ("reference_type", "reference_id", "delivery_user", "route", "status", "assigned_at", "delivered_at")
    list_filter = ("status", "tenant", "assigned_at")


@admin.register(WarehouseRoute)
class WarehouseRouteAdmin(TenantAdmin):
    list_display = ("source_branch", "destination_branch", "priority", "lead_time_hours", "tenant", "is_active")


@admin.register(ForecastModel)
class ForecastModelAdmin(TenantAdmin):
    list_display = ("key", "name", "forecast_type", "horizon_days", "last_run_at", "tenant", "is_active")
    list_filter = ("forecast_type", "tenant", "is_active")

