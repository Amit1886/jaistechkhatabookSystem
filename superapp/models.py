from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BusinessUnit(TimeStampedModel):
    class BusinessType(models.TextChoices):
        RETAIL = "retail", "Retail"
        RESTAURANT = "restaurant", "Restaurant"
        WHOLESALE = "wholesale", "Wholesale"
        ECOMMERCE = "ecommerce", "Ecommerce"
        SERVICE = "service", "Service"
        HYBRID = "hybrid", "Hybrid"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="super_business_units")
    name = models.CharField(max_length=160)
    business_type = models.CharField(max_length=24, choices=BusinessType.choices, default=BusinessType.HYBRID, db_index=True)
    gstin = models.CharField(max_length=15, blank=True, default="", db_index=True)
    state_code = models.CharField(max_length=2, blank=True, default="", db_index=True)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["owner", "business_type", "is_active"])]

    def __str__(self):
        return self.name


class SuperAppModule(TimeStampedModel):
    key = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=80, blank=True, default="", db_index=True)
    route_name = models.CharField(max_length=160, blank=True, default="")
    api_namespace = models.CharField(max_length=160, blank=True, default="")
    role_keys = models.JSONField(default=list, blank=True)
    feature_flags = models.JSONField(default=dict, blank=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class CustomerWallet(TimeStampedModel):
    customer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_smart_wallet")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_wallets")
    cashback_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    reward_points = models.PositiveIntegerField(default=0)
    referral_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gift_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    promo_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    store_credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    loyalty_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=10, default="INR")
    tier = models.CharField(max_length=20, default="silver", db_index=True)
    fraud_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    is_locked = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    @property
    def usable_balance(self):
        return (
            self.cashback_balance
            + self.referral_balance
            + self.gift_balance
            + self.promo_balance
            + self.store_credit
            + self.loyalty_balance
        )

    def __str__(self):
        return f"{self.customer_id}: {self.usable_balance}"


class WalletTransaction(TimeStampedModel):
    class EntryType(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"
        HOLD = "hold", "Hold"
        RELEASE = "release", "Release"

    class Bucket(models.TextChoices):
        CASHBACK = "cashback", "Cashback"
        REWARD = "reward", "Reward"
        REFERRAL = "referral", "Referral"
        GIFT = "gift", "Gift"
        PROMO = "promo", "Promo"
        STORE_CREDIT = "store_credit", "Store Credit"
        LOYALTY = "loyalty", "Loyalty"

    wallet = models.ForeignKey(CustomerWallet, on_delete=models.CASCADE, related_name="transactions")
    entry_type = models.CharField(max_length=12, choices=EntryType.choices, db_index=True)
    bucket = models.CharField(max_length=20, choices=Bucket.choices, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    points = models.IntegerField(default=0)
    channel = models.CharField(max_length=30, default="pos", db_index=True)
    source = models.CharField(max_length=80, default="manual", db_index=True)
    reference = models.CharField(max_length=140, blank=True, default="", db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["wallet", "bucket", "created_at"]),
            models.Index(fields=["channel", "source"]),
        ]


class RewardPoint(TimeStampedModel):
    wallet = models.ForeignKey(CustomerWallet, on_delete=models.CASCADE, related_name="reward_point_entries")
    points = models.IntegerField()
    reason = models.CharField(max_length=80, db_index=True)
    reference = models.CharField(max_length=140, blank=True, default="", db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)


class CashbackRule(TimeStampedModel):
    name = models.CharField(max_length=140)
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="cashback_rules")
    min_order_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cashback_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    max_cashback = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    channel = models.CharField(max_length=30, blank=True, default="", db_index=True)
    tier = models.CharField(max_length=20, blank=True, default="", db_index=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    def is_valid_now(self):
        now = timezone.now()
        return self.is_active and (not self.valid_from or self.valid_from <= now) and (not self.valid_until or now <= self.valid_until)


class GiftCard(TimeStampedModel):
    code = models.CharField(max_length=40, unique=True, db_index=True)
    issued_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="gift_cards")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    original_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)


class EMIPlan(TimeStampedModel):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="emi_plans")
    principal_amount = models.DecimalField(max_digits=14, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    tenure_months = models.PositiveIntegerField(default=1)
    monthly_installment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    partner_finance = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=30, default="draft", db_index=True)
    next_due_date = models.DateField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)


class ReferralBonus(TimeStampedModel):
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="super_referral_bonuses")
    referred = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="super_referred_bonus")
    wallet = models.ForeignKey(CustomerWallet, on_delete=models.SET_NULL, null=True, blank=True, related_name="referral_bonuses")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    points = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=30, default="pending", db_index=True)
    reference = models.CharField(max_length=140, blank=True, default="", db_index=True)


class TaxRule(TimeStampedModel):
    name = models.CharField(max_length=140)
    hsn_sac = models.CharField(max_length=12, blank=True, default="", db_index=True)
    product_category = models.CharField(max_length=120, blank=True, default="", db_index=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, db_index=True)
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    supply_type = models.CharField(max_length=20, default="goods", db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)


class GSTCategory(TimeStampedModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40, unique=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    description = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)


class EInvoice(TimeStampedModel):
    invoice_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    invoice_number = models.CharField(max_length=100, db_index=True)
    seller_gstin = models.CharField(max_length=15, blank=True, default="", db_index=True)
    buyer_gstin = models.CharField(max_length=15, blank=True, default="", db_index=True)
    irn = models.CharField(max_length=120, blank=True, default="", db_index=True)
    qr_payload = models.JSONField(default=dict, blank=True)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=30, default="draft", db_index=True)
    source_type = models.CharField(max_length=80, blank=True, default="", db_index=True)
    source_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    validation_payload = models.JSONField(default=dict, blank=True)


class TaxAlert(TimeStampedModel):
    severity = models.CharField(max_length=20, default="warning", db_index=True)
    alert_type = models.CharField(max_length=80, db_index=True)
    message = models.CharField(max_length=260)
    reference = models.CharField(max_length=140, blank=True, default="", db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)


class TaxReport(TimeStampedModel):
    report_type = models.CharField(max_length=40, db_index=True)
    period = models.CharField(max_length=20, db_index=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="super_tax_reports")
    data = models.JSONField(default=dict, blank=True)
    export_file = models.FileField(upload_to="tax_reports/", blank=True, null=True)

    class Meta:
        unique_together = ("report_type", "period")


class ExpenseScan(TimeStampedModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expense_scans")
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="expense_scans")
    file = models.FileField(upload_to="expense_scans/", blank=True, null=True)
    status = models.CharField(max_length=30, default="uploaded", db_index=True)
    vendor_name = models.CharField(max_length=180, blank=True, default="", db_index=True)
    gstin = models.CharField(max_length=15, blank=True, default="", db_index=True)
    invoice_number = models.CharField(max_length=100, blank=True, default="", db_index=True)
    invoice_date = models.DateField(null=True, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    category_hint = models.CharField(max_length=120, blank=True, default="")
    duplicate_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="duplicates")
    metadata = models.JSONField(default=dict, blank=True)


class OCRResult(TimeStampedModel):
    expense_scan = models.OneToOneField(ExpenseScan, on_delete=models.CASCADE, related_name="ocr_result")
    raw_text = models.TextField(blank=True, default="")
    parsed_payload = models.JSONField(default=dict, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)


class VendorMatch(TimeStampedModel):
    expense_scan = models.ForeignKey(ExpenseScan, on_delete=models.CASCADE, related_name="vendor_matches")
    vendor_name = models.CharField(max_length=180)
    vendor_reference = models.CharField(max_length=140, blank=True, default="")
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict, blank=True)


class ExpenseApproval(TimeStampedModel):
    expense_scan = models.ForeignKey(ExpenseScan, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="expense_scan_approvals")
    level = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, default="pending", db_index=True)
    note = models.TextField(blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)


class ExpenseAttachment(TimeStampedModel):
    expense_scan = models.ForeignKey(ExpenseScan, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="expense_attachments/")
    label = models.CharField(max_length=120, blank=True, default="")


class RestaurantTable(TimeStampedModel):
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.CASCADE, related_name="restaurant_tables")
    table_number = models.CharField(max_length=30)
    seats = models.PositiveIntegerField(default=2)
    qr_token = models.CharField(max_length=80, unique=True, default=uuid.uuid4)
    status = models.CharField(max_length=30, default="available", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("business_unit", "table_number")


class MenuCategory(TimeStampedModel):
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.CASCADE, related_name="menu_categories")
    name = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["sort_order", "name"]


class MenuItem(TimeStampedModel):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80, blank=True, default="", db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    prep_minutes = models.PositiveIntegerField(default=10)
    is_available = models.BooleanField(default=True, db_index=True)
    modifiers = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)


class TableOrder(TimeStampedModel):
    table = models.ForeignKey(RestaurantTable, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="table_orders")
    order_number = models.CharField(max_length=60, unique=True, db_index=True)
    status = models.CharField(max_length=30, default="placed", db_index=True)
    items = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True, default="")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=30, default="unpaid", db_index=True)
    payment_payload = models.JSONField(default=dict, blank=True)


class KitchenQueue(TimeStampedModel):
    order = models.OneToOneField(TableOrder, on_delete=models.CASCADE, related_name="kitchen_queue")
    priority = models.PositiveIntegerField(default=5, db_index=True)
    status = models.CharField(max_length=30, default="new", db_index=True)
    cooking_started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="kitchen_tasks")
    timer_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["priority", "created_at"]


class OrderStatusLog(TimeStampedModel):
    order = models.ForeignKey(TableOrder, on_delete=models.CASCADE, related_name="status_logs")
    previous_status = models.CharField(max_length=30, blank=True, default="")
    new_status = models.CharField(max_length=30, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=220, blank=True, default="")


class SuperDashboardSnapshot(TimeStampedModel):
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name="dashboard_snapshots")
    period = models.CharField(max_length=20, db_index=True)
    sales_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    inventory_alerts = models.PositiveIntegerField(default=0)
    wallet_liability = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    crm_leads = models.PositiveIntegerField(default=0)
    tax_alerts = models.PositiveIntegerField(default=0)
    restaurant_open_orders = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict, blank=True)


class ActivityAuditLog(TimeStampedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="super_activity_logs")
    action = models.CharField(max_length=120, db_index=True)
    module = models.CharField(max_length=80, db_index=True)
    reference = models.CharField(max_length=140, blank=True, default="", db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

