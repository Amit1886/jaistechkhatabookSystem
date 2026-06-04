import uuid
from decimal import Decimal

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
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_records")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class WhiteLabelProfile(TenantScopedModel):
    brand_name = models.CharField(max_length=180)
    logo = models.ImageField(upload_to="tenant_branding/logos/", null=True, blank=True)
    primary_color = models.CharField(max_length=20, default="#2563eb")
    secondary_color = models.CharField(max_length=20, default="#0f172a")
    accent_color = models.CharField(max_length=20, default="#22c55e")
    sidebar_config = models.JSONField(default=dict, blank=True)
    module_config = models.JSONField(default=dict, blank=True)
    invoice_template = models.CharField(max_length=120, blank=True, default="")
    permission_template = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "saas_white_label_profiles"
        unique_together = ("tenant", "brand_name")

    def __str__(self):
        return self.brand_name


class TenantDomain(TenantScopedModel):
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    is_primary = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    ssl_status = models.CharField(max_length=40, default="pending", db_index=True)
    verification_token = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        db_table = "saas_tenant_domains"
        ordering = ("domain",)


class SaaSPlan(TimestampedModel):
    class Interval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=140, unique=True, db_index=True)
    name = models.CharField(max_length=180)
    interval = models.CharField(max_length=20, choices=Interval.choices, default=Interval.MONTHLY)
    base_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="INR")
    features = models.JSONField(default=dict, blank=True)
    limits = models.JSONField(default=dict, blank=True)
    trial_days = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "saas_plans"
        ordering = ("base_price", "name")

    def __str__(self):
        return self.name


class TenantSubscription(TenantScopedModel):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    plan = models.ForeignKey(SaaSPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL, db_index=True)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    payment_provider = models.CharField(max_length=60, blank=True, default="")
    provider_subscription_id = models.CharField(max_length=160, blank=True, default="", db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "saas_tenant_subscriptions"
        indexes = [models.Index(fields=["tenant", "status"])]


class UsageMetric(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=140, unique=True, db_index=True)
    name = models.CharField(max_length=180)
    unit = models.CharField(max_length=40, default="count")
    billable = models.BooleanField(default=False)
    unit_price = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        db_table = "saas_usage_metrics"
        ordering = ("key",)


class UsageRecord(TenantScopedModel):
    metric = models.ForeignKey(UsageMetric, on_delete=models.PROTECT, related_name="usage_records")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    period = models.CharField(max_length=20, db_index=True)
    source_type = models.CharField(max_length=120, blank=True, default="")
    source_id = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        db_table = "saas_usage_records"
        indexes = [models.Index(fields=["tenant", "metric", "period"])]


class SaaSInvoice(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        VOID = "void", "Void"

    subscription = models.ForeignKey(TenantSubscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="saas_invoices")
    invoice_number = models.CharField(max_length=40, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    line_items = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "saas_invoices"
        ordering = ("-created_at",)


class PaymentRetry(TenantScopedModel):
    invoice = models.ForeignKey(SaaSInvoice, on_delete=models.CASCADE, related_name="payment_retries")
    attempt_no = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, default="pending", db_index=True)
    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "saas_payment_retries"
        unique_together = ("invoice", "attempt_no")


class EcosystemPartner(TenantScopedModel):
    class PartnerType(models.TextChoices):
        PLATFORM = "platform", "Platform"
        RESELLER = "reseller", "Reseller"
        FRANCHISE = "franchise", "Franchise"
        SUPER_STOCKIST = "super_stockist", "Super Stockist"
        DISTRIBUTOR = "distributor", "Distributor"
        DEALER = "dealer", "Dealer"
        RETAILER = "retailer", "Retailer"
        CUSTOMER = "customer", "Customer"

    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="ecosystem_partners")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="ecosystem_partners")
    partner_type = models.CharField(max_length=40, choices=PartnerType.choices, db_index=True)
    code = models.CharField(max_length=80, db_index=True)
    name = models.CharField(max_length=180)
    contact_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="ecosystem_partners")
    commission_rules = models.JSONField(default=dict, blank=True)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    territory = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "saas_ecosystem_partners"
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "partner_type", "is_active"])]

    def __str__(self):
        return f"{self.code} - {self.name}"


class FranchiseAgreement(TenantScopedModel):
    partner = models.ForeignKey(EcosystemPartner, on_delete=models.CASCADE, related_name="franchise_agreements")
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    royalty_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    terms = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "saas_franchise_agreements"


class RoutePlan(TenantScopedModel):
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=80, db_index=True)
    owner = models.ForeignKey(EcosystemPartner, on_delete=models.SET_NULL, null=True, blank=True, related_name="route_plans")
    salesman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="route_plans")
    schedule = models.JSONField(default=dict, blank=True)
    stops = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "ops_route_plans"
        unique_together = ("tenant", "code")


class SalesmanTracking(TenantScopedModel):
    salesman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="salesman_tracking_points")
    route = models.ForeignKey(RoutePlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="tracking_points")
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy_meters = models.PositiveIntegerField(default=0)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "ops_salesman_tracking"
        ordering = ("-recorded_at",)


class VanSalesSession(TenantScopedModel):
    route = models.ForeignKey(RoutePlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="van_sessions")
    salesman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="van_sales_sessions")
    vehicle_no = models.CharField(max_length=80, blank=True, default="")
    opening_stock = models.JSONField(default=list, blank=True)
    closing_stock = models.JSONField(default=list, blank=True)
    cash_collected = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default="open", db_index=True)

    class Meta:
        db_table = "ops_van_sales_sessions"


class DeliveryAssignment(TenantScopedModel):
    route = models.ForeignKey(RoutePlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_assignments")
    delivery_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="delivery_assignments")
    reference_type = models.CharField(max_length=120, db_index=True)
    reference_id = models.CharField(max_length=120, db_index=True)
    status = models.CharField(max_length=40, default="assigned", db_index=True)
    proof = models.JSONField(default=dict, blank=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ops_delivery_assignments"


class WarehouseRoute(TenantScopedModel):
    source_branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="outbound_warehouse_routes")
    destination_branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="inbound_warehouse_routes")
    priority = models.PositiveIntegerField(default=100)
    lead_time_hours = models.PositiveIntegerField(default=24)
    rules = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "ops_warehouse_routes"


class ForecastModel(TenantScopedModel):
    key = models.SlugField(max_length=140, db_index=True)
    name = models.CharField(max_length=180)
    forecast_type = models.CharField(max_length=60, default="inventory", db_index=True)
    horizon_days = models.PositiveIntegerField(default=30)
    parameters = models.JSONField(default=dict, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "ops_forecast_models"
        unique_together = ("tenant", "key")

