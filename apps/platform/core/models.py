import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.platform.identity.models import Branch, Company, Tenant


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="%(class)s_records")
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True


class IndustryBlueprint(TenantScopedModel):
    class Industry(models.TextChoices):
        RETAIL = "retail", "Retail"
        RESTAURANT = "restaurant", "Restaurant"
        PHARMACY = "pharmacy", "Pharmacy"
        GROCERY = "grocery", "Grocery"
        GARMENT = "garment", "Garment"
        FOOTWEAR = "footwear", "Footwear"
        HOTEL = "hotel", "Hotel"
        MANUFACTURING = "manufacturing", "Manufacturing"
        DISTRIBUTION = "distribution", "Distribution"

    key = models.SlugField(max_length=120, db_index=True)
    name = models.CharField(max_length=180)
    industry = models.CharField(max_length=40, choices=Industry.choices, db_index=True)
    description = models.TextField(blank=True, default="")
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_industry_blueprints"
        unique_together = ("tenant", "key")
        ordering = ("industry", "name")

    def __str__(self):
        return self.name


class FeatureToggle(TenantScopedModel):
    key = models.SlugField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=True, db_index=True)
    rollout_percent = models.PositiveSmallIntegerField(default=100)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    conditions = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_feature_toggles"
        unique_together = ("tenant", "key")
        ordering = ("key",)

    def is_enabled_now(self):
        now = timezone.now()
        return self.enabled and (self.starts_at is None or self.starts_at <= now) and (self.ends_at is None or self.ends_at >= now)


class ModuleDefinition(TenantScopedModel):
    key = models.SlugField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    domain = models.CharField(max_length=80, db_index=True)
    version = models.PositiveIntegerField(default=1)
    blueprint = models.ForeignKey(IndustryBlueprint, on_delete=models.SET_NULL, null=True, blank=True, related_name="modules")
    schema = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_modules"
        unique_together = ("tenant", "key")
        ordering = ("domain", "name")

    def __str__(self):
        return self.name


class MenuItem(TenantScopedModel):
    module = models.ForeignKey(ModuleDefinition, on_delete=models.CASCADE, null=True, blank=True, related_name="menu_items")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    key = models.SlugField(max_length=180, db_index=True)
    label = models.CharField(max_length=180)
    icon = models.CharField(max_length=80, blank=True, default="")
    route_name = models.CharField(max_length=180, blank=True, default="")
    url = models.CharField(max_length=260, blank=True, default="")
    permission_key = models.CharField(max_length=180, blank=True, default="", db_index=True)
    sort_order = models.PositiveIntegerField(default=100)
    visibility_rules = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_menu_items"
        unique_together = ("tenant", "key")
        ordering = ("sort_order", "label")

    def __str__(self):
        return self.label


class FormDefinition(TenantScopedModel):
    module = models.ForeignKey(ModuleDefinition, on_delete=models.CASCADE, related_name="forms")
    key = models.SlugField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    model_path = models.CharField(max_length=220, blank=True, default="")
    layout = models.JSONField(default=dict, blank=True)
    validation_schema = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "platform_core_forms"
        unique_together = ("tenant", "key")
        ordering = ("module__key", "name")


class FormFieldDefinition(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(FormDefinition, on_delete=models.CASCADE, related_name="fields")
    key = models.SlugField(max_length=160)
    label = models.CharField(max_length=180)
    field_type = models.CharField(max_length=60, db_index=True)
    data_source = models.JSONField(default=dict, blank=True)
    default_value = models.JSONField(default=dict, blank=True)
    validation_rules = models.JSONField(default=dict, blank=True)
    permission_key = models.CharField(max_length=180, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=100)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_form_fields"
        unique_together = ("form", "key")
        ordering = ("sort_order", "label")


class WorkflowDefinition(TenantScopedModel):
    module = models.ForeignKey(ModuleDefinition, on_delete=models.CASCADE, related_name="workflows")
    key = models.SlugField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    applies_to = models.CharField(max_length=220, blank=True, default="")
    start_state = models.CharField(max_length=120)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "platform_core_workflows"
        unique_together = ("tenant", "key")
        ordering = ("module__key", "name")


class WorkflowState(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name="states")
    key = models.SlugField(max_length=120)
    label = models.CharField(max_length=160)
    state_type = models.CharField(max_length=40, default="normal", db_index=True)
    sort_order = models.PositiveIntegerField(default=100)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_workflow_states"
        unique_together = ("workflow", "key")
        ordering = ("sort_order", "label")


class WorkflowTransition(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name="transitions")
    key = models.SlugField(max_length=160)
    label = models.CharField(max_length=180)
    from_state = models.CharField(max_length=120)
    to_state = models.CharField(max_length=120)
    permission_key = models.CharField(max_length=180, blank=True, default="")
    conditions = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "platform_core_workflow_transitions"
        unique_together = ("workflow", "key")


class ReportDefinition(TenantScopedModel):
    module = models.ForeignKey(ModuleDefinition, on_delete=models.CASCADE, related_name="reports")
    key = models.SlugField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    report_type = models.CharField(max_length=60, default="table", db_index=True)
    query_spec = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    filters = models.JSONField(default=list, blank=True)
    permission_key = models.CharField(max_length=180, blank=True, default="")

    class Meta:
        db_table = "platform_core_reports"
        unique_together = ("tenant", "key")
        ordering = ("module__key", "name")


class DashboardDefinition(TenantScopedModel):
    key = models.SlugField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    layout = models.JSONField(default=dict, blank=True)
    filters = models.JSONField(default=list, blank=True)
    permission_key = models.CharField(max_length=180, blank=True, default="")

    class Meta:
        db_table = "platform_core_dashboards"
        unique_together = ("tenant", "key")
        ordering = ("name",)


class DashboardWidget(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(DashboardDefinition, on_delete=models.CASCADE, related_name="widgets")
    key = models.SlugField(max_length=160)
    title = models.CharField(max_length=180)
    widget_type = models.CharField(max_length=60, db_index=True)
    data_source = models.JSONField(default=dict, blank=True)
    layout = models.JSONField(default=dict, blank=True)
    refresh_seconds = models.PositiveIntegerField(default=60)
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_dashboard_widgets"
        unique_together = ("dashboard", "key")
        ordering = ("sort_order", "title")


class EventSubscription(TenantScopedModel):
    event_type = models.CharField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    handler_type = models.CharField(max_length=80, db_index=True)
    handler_config = models.JSONField(default=dict, blank=True)
    conditions = models.JSONField(default=dict, blank=True)
    priority = models.PositiveIntegerField(default=100)

    class Meta:
        db_table = "platform_core_event_subscriptions"
        ordering = ("event_type", "priority")


class AutomationRule(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"

    key = models.SlugField(max_length=160, db_index=True)
    name = models.CharField(max_length=180)
    trigger_event = models.CharField(max_length=160, db_index=True)
    conditions = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    run_as = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="automation_rules")

    class Meta:
        db_table = "platform_core_automation_rules"
        unique_together = ("tenant", "key")
        ordering = ("trigger_event", "name")


class AutomationRun(TimestampedModel):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="automation_runs")
    rule = models.ForeignKey(AutomationRule, on_delete=models.SET_NULL, null=True, blank=True, related_name="runs")
    event_type = models.CharField(max_length=160, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "platform_core_automation_runs"
        ordering = ("-created_at",)


class Product(TenantScopedModel):
    class ProductType(models.TextChoices):
        GOODS = "goods", "Goods"
        SERVICE = "service", "Service"
        COMPOSITE = "composite", "Composite"

    sku = models.CharField(max_length=120, db_index=True)
    name = models.CharField(max_length=220)
    product_type = models.CharField(max_length=30, choices=ProductType.choices, default=ProductType.GOODS)
    category = models.CharField(max_length=160, blank=True, default="", db_index=True)
    tax_code = models.CharField(max_length=60, blank=True, default="")
    uom = models.CharField(max_length=40, default="pcs")
    
    image = models.ImageField(
    upload_to="products/",
    blank=True,
    null=True
)

sale_price = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
)

description = models.TextField(
    blank=True,
    default=""
)

is_featured = models.BooleanField(
    default=False
)

class Meta:
        db_table = "platform_inventory_products"
        unique_together = ("tenant", "sku")
        ordering = ("name",)

def __str__(self):
        return self.name


class ProductAttribute(TenantScopedModel):
    key = models.SlugField(max_length=120, db_index=True)
    name = models.CharField(max_length=160)
    values = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "platform_inventory_attributes"
        unique_together = ("tenant", "key")
        ordering = ("name",)


class ProductVariant(TenantScopedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=120, db_index=True)
    barcode = models.CharField(max_length=120, blank=True, default="", db_index=True)
    attributes = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "platform_inventory_variants"
        unique_together = ("tenant", "sku")
        ordering = ("product__name", "sku")


class Warehouse(TenantScopedModel):
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="core_warehouses")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="core_warehouses")
    code = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=180)

    class Meta:
        db_table = "platform_inventory_warehouses"
        unique_together = ("tenant", "code")
        ordering = ("name",)


class StockLedgerEntry(TimestampedModel):
    class MovementType(models.TextChoices):
        OPENING = "opening", "Opening"
        PURCHASE = "purchase", "Purchase"
        SALE = "sale", "Sale"
        TRANSFER = "transfer", "Transfer"
        ADJUSTMENT = "adjustment", "Adjustment"
        PRODUCTION = "production", "Production"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="stock_ledger_entries")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_entries")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_entries")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_entries")
    movement_type = models.CharField(max_length=30, choices=MovementType.choices, db_index=True)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    batch_no = models.CharField(max_length=120, blank=True, default="", db_index=True)
    serial_no = models.CharField(max_length=160, blank=True, default="", db_index=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    reference_type = models.CharField(max_length=120, blank=True, default="", db_index=True)
    reference_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    posted_at = models.DateTimeField(default=timezone.now, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_inventory_stock_ledger"
        ordering = ("-posted_at",)
        indexes = [
            models.Index(fields=["tenant", "product", "posted_at"]),
            models.Index(fields=["tenant", "warehouse", "posted_at"]),
        ]


class StockTransfer(TenantScopedModel):
    reference_no = models.CharField(max_length=120, db_index=True)
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="outgoing_transfers")
    destination_warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="incoming_transfers")
    status = models.CharField(max_length=40, default="draft", db_index=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_inventory_stock_transfers"
        unique_together = ("tenant", "reference_no")


class ProcurementRequest(TenantScopedModel):
    reference_no = models.CharField(max_length=120, db_index=True)
    supplier_name = models.CharField(max_length=180, blank=True, default="")
    status = models.CharField(max_length=40, default="draft", db_index=True)
    expected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_inventory_procurement_requests"
        unique_together = ("tenant", "reference_no")


class BillOfMaterials(TenantScopedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="boms")
    version = models.PositiveIntegerField(default=1)
    output_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=1)
    components = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "platform_inventory_bom"
        unique_together = ("tenant", "product", "version")


class ChartOfAccount(TenantScopedModel):
    class AccountType(models.TextChoices):
        ASSET = "asset", "Asset"
        LIABILITY = "liability", "Liability"
        EQUITY = "equity", "Equity"
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    code = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=180)
    account_type = models.CharField(max_length=30, choices=AccountType.choices, db_index=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    gst_applicable = models.BooleanField(default=False)

    class Meta:
        db_table = "platform_financial_chart_of_accounts"
        unique_together = ("tenant", "code")
        ordering = ("code",)


class JournalEntry(TenantScopedModel):
    reference_no = models.CharField(max_length=120, db_index=True)
    entry_date = models.DateField(default=timezone.localdate, db_index=True)
    source_type = models.CharField(max_length=120, blank=True, default="", db_index=True)
    source_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    status = models.CharField(max_length=40, default="draft", db_index=True)
    narration = models.TextField(blank=True, default="")
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="core_journal_entries")

    class Meta:
        db_table = "platform_financial_journal_entries"
        unique_together = ("tenant", "reference_no")
        ordering = ("-entry_date", "-created_at")


class JournalLine(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    party_type = models.CharField(max_length=80, blank=True, default="")
    party_id = models.CharField(max_length=120, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_financial_journal_lines"
        indexes = [models.Index(fields=["account", "created_at"])]


class GSTLedgerEntry(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="gst_ledger_entries")
    journal = models.ForeignKey(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name="gst_entries")
    gstin = models.CharField(max_length=32, blank=True, default="", db_index=True)
    tax_type = models.CharField(max_length=40, db_index=True)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    period = models.CharField(max_length=20, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_financial_gst_ledger"
        ordering = ("-created_at",)


class PolicyDefinition(TenantScopedModel):
    class PolicyType(models.TextChoices):
        ROLE = "role", "Role"
        FIELD = "field", "Field"
        TENANT = "tenant", "Tenant"
        PRICING = "pricing", "Pricing"
        WORKFLOW = "workflow", "Workflow"
        TAX = "tax", "Tax"
        APPROVAL = "approval", "Approval"

    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    policy_type = models.CharField(max_length=40, choices=PolicyType.choices, db_index=True)
    priority = models.PositiveIntegerField(default=100)
    conditions = models.JSONField(default=dict, blank=True)
    effect = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "platform_core_policies"
        unique_together = ("tenant", "key")
        ordering = ("policy_type", "priority", "name")


class RuleDefinition(TenantScopedModel):
    class RuleType(models.TextChoices):
        BUSINESS = "business", "Business"
        PRICING = "pricing", "Pricing"
        TAX = "tax", "Tax"
        APPROVAL = "approval", "Approval"
        AUTOMATION = "automation", "Automation"
        VALIDATION = "validation", "Validation"

    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    rule_type = models.CharField(max_length=40, choices=RuleType.choices, db_index=True)
    when = models.JSONField(default=dict, blank=True)
    then = models.JSONField(default=dict, blank=True)
    priority = models.PositiveIntegerField(default=100)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "platform_core_rules"
        unique_together = ("tenant", "key")
        ordering = ("rule_type", "priority", "name")


class CommandEnvelope(TimestampedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        ACCEPTED = "accepted", "Accepted"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="command_envelopes")
    command_type = models.CharField(max_length=180, db_index=True)
    idempotency_key = models.CharField(max_length=180, blank=True, default="", db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="core_commands")
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "platform_core_command_envelopes"
        indexes = [models.Index(fields=["tenant", "command_type", "created_at"])]


class QueryDefinition(TenantScopedModel):
    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    query_type = models.CharField(max_length=80, default="read_model", db_index=True)
    source = models.JSONField(default=dict, blank=True)
    projection = models.JSONField(default=list, blank=True)
    filters = models.JSONField(default=list, blank=True)
    permission_key = models.CharField(max_length=180, blank=True, default="")
    cache_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "platform_core_query_definitions"
        unique_together = ("tenant", "key")
        ordering = ("name",)


class BackgroundJobDefinition(TenantScopedModel):
    class Queue(models.TextChoices):
        DEFAULT = "default", "Default"
        NOTIFICATIONS = "notifications", "Notifications"
        REPORTS = "reports", "Reports"
        AI = "ai", "AI"
        OCR = "ocr", "OCR"
        EXPORTS = "exports", "Exports"
        INTEGRATIONS = "integrations", "Integrations"

    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    task_path = models.CharField(max_length=260)
    queue = models.CharField(max_length=40, choices=Queue.choices, default=Queue.DEFAULT, db_index=True)
    schedule = models.JSONField(default=dict, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=300)
    max_retries = models.PositiveIntegerField(default=3)

    class Meta:
        db_table = "platform_core_background_jobs"
        unique_together = ("tenant", "key")
        ordering = ("queue", "name")


class IntegrationEndpoint(TenantScopedModel):
    class EndpointType(models.TextChoices):
        WEBHOOK = "webhook", "Webhook"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        API = "api", "API"
        ANALYTICS = "analytics", "Analytics"
        AI = "ai", "AI"

    key = models.SlugField(max_length=180, db_index=True)
    name = models.CharField(max_length=220)
    endpoint_type = models.CharField(max_length=40, choices=EndpointType.choices, db_index=True)
    target_url = models.CharField(max_length=500, blank=True, default="")
    auth_config = models.JSONField(default=dict, blank=True)
    event_types = models.JSONField(default=list, blank=True)
    rate_limit = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_integration_endpoints"
        unique_together = ("tenant", "key")
        ordering = ("endpoint_type", "name")


class ObservabilityEvent(TimestampedModel):
    class EventType(models.TextChoices):
        REQUEST = "request", "Request"
        TRACE = "trace", "Trace"
        AUDIT = "audit", "Audit"
        PERFORMANCE = "performance", "Performance"
        SLOW_QUERY = "slow_query", "Slow Query"
        HEALTH = "health", "Health"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="observability_events")
    event_type = models.CharField(max_length=40, choices=EventType.choices, db_index=True)
    trace_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    name = models.CharField(max_length=220, db_index=True)
    duration_ms = models.PositiveIntegerField(default=0)
    severity = models.CharField(max_length=20, default="info", db_index=True)
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "platform_core_observability_events"
        ordering = ("-created_at",)
