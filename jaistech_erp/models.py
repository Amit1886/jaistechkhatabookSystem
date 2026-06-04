from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Business(TimeStampedModel):
    name = models.CharField(max_length=160, unique=True)
    legal_name = models.CharField(max_length=180, blank=True, default="")
    gst_number = models.CharField(max_length=24, blank=True, default="")
    mobile = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    settings = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Store(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="stores")
    name = models.CharField(max_length=140)
    code = models.SlugField(max_length=60)
    store_type = models.CharField(max_length=40, default="retail")
    address = models.TextField(blank=True, default="")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = ("business", "code")
        ordering = ["business", "name"]

    def __str__(self):
        return f"{self.business} - {self.name}"


class Module(TimeStampedModel):
    key = models.SlugField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=60, default="apps")
    color = models.CharField(max_length=20, default="#2563EB")
    api_base = models.CharField(max_length=160, blank=True, default="")
    app_route = models.CharField(max_length=120, blank=True, default="")
    schema = models.JSONField(default=dict, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=100)
    is_core = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["order", "name"]

    def save(self, *args, **kwargs):
        if not self.api_base:
            self.api_base = f"/api/{self.key}/"
        if not self.app_route:
            self.app_route = f"/module/{self.key}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Permission(TimeStampedModel):
    ACTIONS = (
        ("list", "List"),
        ("retrieve", "Retrieve"),
        ("create", "Create"),
        ("update", "Update"),
        ("partial_update", "Partial update"),
        ("destroy", "Delete"),
        ("export", "Export"),
        ("sync", "Sync"),
    )
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="permissions")
    action = models.CharField(max_length=40, choices=ACTIONS)
    key = models.SlugField(max_length=140, unique=True, db_index=True)
    label = models.CharField(max_length=160)

    class Meta:
        ordering = ["module__order", "module__name", "action"]
        unique_together = ("module", "action")

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = f"{self.module.key}_{self.action}"
        if not self.label:
            self.label = f"{self.module.name} {self.action.replace('_', ' ').title()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


class Role(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="roles", null=True, blank=True)
    key = models.SlugField(max_length=80, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    permissions = models.ManyToManyField(Permission, blank=True, related_name="roles")
    is_admin = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)

    class Meta:
        unique_together = ("business", "key")
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserBusinessMembership(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jaistech_memberships")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="memberships")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships")
    stores = models.ManyToManyField(Store, blank=True, related_name="memberships")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = ("user", "business")

    def __str__(self):
        return f"{self.user} @ {self.business}"


class Customer(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=140)
    mobile = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    gst_number = models.CharField(max_length=24, blank=True, default="")
    address = models.TextField(blank=True, default="")
    loyalty_points = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="products")
    sku = models.CharField(max_length=80, db_index=True)
    barcode = models.CharField(max_length=80, blank=True, default="", db_index=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=120, blank=True, default="")
    unit = models.CharField(max_length=30, default="pcs")
    sale_price = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    stock_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    low_stock_qty = models.DecimalField(max_digits=12, decimal_places=2, default=5)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = ("business", "sku")
        ordering = ["name"]

    @property
    def is_low_stock(self):
        return self.stock_qty <= self.low_stock_qty

    def __str__(self):
        return self.name


class Invoice(TimeStampedModel):
    STATUS_CHOICES = (("draft", "Draft"), ("paid", "Paid"), ("partial", "Partial"), ("void", "Void"))
    CHANNEL_CHOICES = (("pos", "POS"), ("ecommerce", "eCommerce"), ("self_checkout", "Self Checkout"), ("b2b", "B2B"))
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="invoices")
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    invoice_number = models.CharField(max_length=40, unique=True)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default="pos")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="paid")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=40, default="cash")
    invoice_date = models.DateField(default=timezone.localdate)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]

    def recalculate(self):
        lines = list(self.lines.all())
        self.subtotal = sum((line.line_total for line in lines), Decimal("0.00"))
        self.tax_total = sum((line.tax_amount for line in lines), Decimal("0.00"))
        self.grand_total = self.subtotal + self.tax_total - self.discount_total

    def __str__(self):
        return self.invoice_number


class InvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=180)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        self.tax_amount = self.line_total * (self.tax_rate / Decimal("100.00"))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.description


class Expense(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="erp_expenses")
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True)
    expense_number = models.CharField(max_length=40, unique=True)
    category = models.CharField(max_length=100, default="General")
    vendor_name = models.CharField(max_length=140, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=40, default="cash")
    expense_date = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-expense_date"]

    def __str__(self):
        return self.expense_number


class LedgerAccount(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="ledger_accounts")
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=140)
    account_type = models.CharField(max_length=40, default="asset")
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = ("business", "code")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class LedgerEntry(TimeStampedModel):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="ledger_entries")
    account = models.ForeignKey(LedgerAccount, on_delete=models.CASCADE, related_name="entries")
    entry_date = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=80, blank=True, default="")
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    memo = models.CharField(max_length=220, blank=True, default="")

    class Meta:
        ordering = ["-entry_date", "-id"]

    def __str__(self):
        return f"{self.account} {self.debit}/{self.credit}"


class CustomEntity(TimeStampedModel):
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name="custom_entity")
    model_key = models.SlugField(max_length=80, unique=True)
    display_name = models.CharField(max_length=140)
    field_schema = models.JSONField(default=list, blank=True)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name


class CustomRecord(TimeStampedModel):
    entity = models.ForeignKey(CustomEntity, on_delete=models.CASCADE, related_name="records")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="custom_records")
    data = models.JSONField(default=dict, blank=True)
    search_text = models.TextField(blank=True, default="", db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        self.search_text = " ".join(str(v) for v in (self.data or {}).values())[:2000]
        super().save(*args, **kwargs)


class SyncQueue(TimeStampedModel):
    STATUS_CHOICES = (("pending", "Pending"), ("synced", "Synced"), ("failed", "Failed"))
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="sync_queue")
    device_id = models.CharField(max_length=120, db_index=True)
    entity = models.CharField(max_length=120)
    operation = models.CharField(max_length=40)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    error = models.TextField(blank=True, default="")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]


class SystemErrorLog(TimeStampedModel):
    SEVERITY_CHOICES = (
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
        ("critical", "Critical"),
    )
    STATUS_CHOICES = (
        ("open", "Open"),
        ("reviewed", "Reviewed"),
        ("resolved", "Resolved"),
        ("ignored", "Ignored"),
    )

    title = models.CharField(max_length=180, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="error", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    source = models.CharField(max_length=80, default="backend", db_index=True)
    endpoint = models.CharField(max_length=240, blank=True, default="", db_index=True)
    method = models.CharField(max_length=12, blank=True, default="")
    status_code = models.PositiveIntegerField(default=500)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    problem = models.TextField()
    root_cause = models.TextField(blank=True, default="")
    recommended_fix = models.TextField(blank=True, default="")
    exception = models.TextField(blank=True, default="")
    traceback = models.TextField(blank=True, default="")
    request_payload = models.JSONField(default=dict, blank=True)
    occurrences = models.PositiveIntegerField(default=1)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_seen_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "severity"]),
            models.Index(fields=["endpoint", "status"]),
        ]

    def __str__(self):
        return f"{self.severity.upper()} {self.title}"
