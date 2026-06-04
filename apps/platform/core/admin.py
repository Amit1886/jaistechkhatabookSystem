from django.contrib import admin

from apps.platform.core.models import (
    AutomationRule,
    AutomationRun,
    BackgroundJobDefinition,
    BillOfMaterials,
    ChartOfAccount,
    CommandEnvelope,
    DashboardDefinition,
    DashboardWidget,
    EventSubscription,
    FeatureToggle,
    FormDefinition,
    FormFieldDefinition,
    GSTLedgerEntry,
    IntegrationEndpoint,
    IndustryBlueprint,
    JournalEntry,
    JournalLine,
    MenuItem,
    ModuleDefinition,
    ObservabilityEvent,
    PolicyDefinition,
    ProcurementRequest,
    Product,
    ProductAttribute,
    ProductVariant,
    QueryDefinition,
    ReportDefinition,
    RuleDefinition,
    StockLedgerEntry,
    StockTransfer,
    Warehouse,
    WorkflowDefinition,
    WorkflowState,
    WorkflowTransition,
)


class TenantAdmin(admin.ModelAdmin):
    list_filter = ("tenant", "is_active")


@admin.register(IndustryBlueprint)
class IndustryBlueprintAdmin(TenantAdmin):
    list_display = ("name", "industry", "tenant", "is_active", "updated_at")
    list_filter = ("industry", "tenant", "is_active")


@admin.register(FeatureToggle)
class FeatureToggleAdmin(TenantAdmin):
    list_display = ("key", "name", "tenant", "enabled", "rollout_percent", "is_active")
    list_filter = ("enabled", "tenant", "is_active")


@admin.register(ModuleDefinition)
class ModuleDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "domain", "tenant", "version", "is_active")
    list_filter = ("domain", "tenant", "is_active")


@admin.register(MenuItem)
class MenuItemAdmin(TenantAdmin):
    list_display = ("label", "key", "module", "parent", "permission_key", "sort_order", "is_active")
    list_filter = ("tenant", "module", "is_active")


class FormFieldInline(admin.TabularInline):
    model = FormFieldDefinition
    extra = 0


@admin.register(FormDefinition)
class FormDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "module", "tenant", "version", "is_active")
    list_filter = ("tenant", "module", "is_active")
    inlines = [FormFieldInline]


@admin.register(FormFieldDefinition)
class FormFieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "form", "field_type", "is_required", "sort_order", "is_active")
    search_fields = ("key", "label", "form__key")
    list_filter = ("field_type", "is_required", "is_active")


class WorkflowStateInline(admin.TabularInline):
    model = WorkflowState
    extra = 0


class WorkflowTransitionInline(admin.TabularInline):
    model = WorkflowTransition
    extra = 0


@admin.register(WorkflowDefinition)
class WorkflowDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "module", "start_state", "version", "is_active")
    list_filter = ("tenant", "module", "is_active")
    inlines = [WorkflowStateInline, WorkflowTransitionInline]


@admin.register(WorkflowState)
class WorkflowStateAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "workflow", "state_type", "sort_order")
    search_fields = ("key", "label", "workflow__key")
    list_filter = ("state_type",)


@admin.register(WorkflowTransition)
class WorkflowTransitionAdmin(admin.ModelAdmin):
    list_display = ("label", "key", "workflow", "from_state", "to_state", "permission_key", "is_active")
    search_fields = ("key", "label", "workflow__key", "permission_key")
    list_filter = ("is_active",)


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "module", "report_type", "permission_key", "is_active")
    list_filter = ("report_type", "tenant", "module", "is_active")


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0


@admin.register(DashboardDefinition)
class DashboardDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "tenant", "permission_key", "is_active")
    inlines = [DashboardWidgetInline]


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("title", "key", "dashboard", "widget_type", "refresh_seconds", "sort_order", "is_active")
    search_fields = ("key", "title", "dashboard__key")
    list_filter = ("widget_type", "is_active")


@admin.register(EventSubscription)
class EventSubscriptionAdmin(TenantAdmin):
    list_display = ("name", "event_type", "handler_type", "tenant", "priority", "is_active")
    list_filter = ("event_type", "handler_type", "tenant", "is_active")


@admin.register(AutomationRule)
class AutomationRuleAdmin(TenantAdmin):
    list_display = ("name", "key", "trigger_event", "status", "tenant", "is_active")
    list_filter = ("status", "trigger_event", "tenant", "is_active")


@admin.register(AutomationRun)
class AutomationRunAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "rule", "tenant", "status")
    search_fields = ("event_type", "rule__key", "error")
    list_filter = ("status", "tenant", "created_at")
    readonly_fields = tuple(field.name for field in AutomationRun._meta.fields)


@admin.register(CommandEnvelope)
class CommandEnvelopeAdmin(admin.ModelAdmin):
    list_display = ("created_at", "command_type", "tenant", "status", "requested_by", "idempotency_key")
    search_fields = ("command_type", "idempotency_key", "requested_by__email", "error")
    list_filter = ("status", "tenant", "created_at")
    readonly_fields = tuple(field.name for field in CommandEnvelope._meta.fields)


@admin.register(BackgroundJobDefinition)
class BackgroundJobDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "task_path", "queue", "tenant", "timeout_seconds", "max_retries", "is_active")
    list_filter = ("queue", "tenant", "is_active")


@admin.register(Product)
class ProductAdmin(TenantAdmin):
    list_display = ("name", "sku", "product_type", "category", "tenant", "is_active")
    list_filter = ("product_type", "category", "tenant", "is_active")


@admin.register(ProductAttribute)
class ProductAttributeAdmin(TenantAdmin):
    list_display = ("name", "key", "tenant", "is_active")


@admin.register(ProductVariant)
class ProductVariantAdmin(TenantAdmin):
    list_display = ("sku", "product", "barcode", "price", "tenant", "is_active")
    search_fields = ("sku", "barcode", "product__name")


@admin.register(Warehouse)
class WarehouseAdmin(TenantAdmin):
    list_display = ("name", "code", "company", "branch", "tenant", "is_active")
    search_fields = ("name", "code", "company__name", "branch__name")


@admin.register(StockLedgerEntry)
class StockLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("posted_at", "movement_type", "product", "warehouse", "quantity", "reference_type", "reference_id")
    search_fields = ("product__name", "warehouse__name", "reference_id", "batch_no", "serial_no")
    list_filter = ("movement_type", "tenant", "warehouse", "posted_at")


@admin.register(StockTransfer)
class StockTransferAdmin(TenantAdmin):
    list_display = ("reference_no", "source_warehouse", "destination_warehouse", "status", "tenant", "is_active")
    list_filter = ("status", "tenant", "is_active")


@admin.register(ProcurementRequest)
class ProcurementRequestAdmin(TenantAdmin):
    list_display = ("reference_no", "supplier_name", "status", "tenant", "expected_at", "is_active")
    list_filter = ("status", "tenant", "is_active")


@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(TenantAdmin):
    list_display = ("product", "version", "output_quantity", "tenant", "is_active")


@admin.register(ChartOfAccount)
class ChartOfAccountAdmin(TenantAdmin):
    list_display = ("code", "name", "account_type", "parent", "tenant", "gst_applicable", "is_active")
    list_filter = ("account_type", "gst_applicable", "tenant", "is_active")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(JournalEntry)
class JournalEntryAdmin(TenantAdmin):
    list_display = ("reference_no", "entry_date", "status", "source_type", "tenant", "posted_by")
    list_filter = ("status", "source_type", "tenant", "entry_date")
    inlines = [JournalLineInline]


@admin.register(JournalLine)
class JournalLineAdmin(admin.ModelAdmin):
    list_display = ("journal", "account", "debit", "credit", "party_type", "party_id")
    search_fields = ("journal__reference_no", "account__name", "party_id")
    list_filter = ("account__account_type",)


@admin.register(GSTLedgerEntry)
class GSTLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "gstin", "tax_type", "taxable_value", "tax_amount", "period", "tenant")
    search_fields = ("gstin", "period", "journal__reference_no")
    list_filter = ("tax_type", "period", "tenant")


@admin.register(PolicyDefinition)
class PolicyDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "policy_type", "priority", "tenant", "version", "is_active")
    list_filter = ("policy_type", "tenant", "is_active")


@admin.register(RuleDefinition)
class RuleDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "rule_type", "priority", "tenant", "version", "is_active")
    list_filter = ("rule_type", "tenant", "is_active")


@admin.register(QueryDefinition)
class QueryDefinitionAdmin(TenantAdmin):
    list_display = ("name", "key", "query_type", "permission_key", "cache_seconds", "tenant", "is_active")
    list_filter = ("query_type", "tenant", "is_active")


@admin.register(IntegrationEndpoint)
class IntegrationEndpointAdmin(TenantAdmin):
    list_display = ("name", "key", "endpoint_type", "tenant", "is_active")
    list_filter = ("endpoint_type", "tenant", "is_active")


@admin.register(ObservabilityEvent)
class ObservabilityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_type", "name", "trace_id", "duration_ms", "severity", "tenant")
    search_fields = ("name", "trace_id")
    list_filter = ("event_type", "severity", "tenant", "created_at")
    readonly_fields = tuple(field.name for field in ObservabilityEvent._meta.fields)
    CommandEnvelope,
