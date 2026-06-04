from django.db import models
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal
import uuid
import random
import string
from khataapp.models import Party, FieldAgent
from django.contrib.auth import get_user_model

User = get_user_model()


@property
def quantity(self):
    return self.qty


# ---------------- Warehouses ----------------
class Warehouse(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255, blank=True, null=True)
    capacity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ---------------- Categories & Products ----------------
class Category(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.owner.email})"

class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, related_name="products", null=True, blank=True
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    min_stock = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True)
    image = models.ImageField(upload_to="product_images/", blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    unit = models.CharField(max_length=50, default="pcs")
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_products",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name

# ---------------- Inventory ----------------
class Inventory(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="inventories"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="inventories")
    stock = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("owner", "product")

    def __str__(self):
        return f"{self.product.name} ({self.owner}) - {self.stock}"


# ---------------- Stock ----------------
class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stocks")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stocks")
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("product", "warehouse")

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.name}: {self.quantity}"


# ---------------- Chat Models ----------------
class ChatThread(models.Model):
    party = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name="chat_threads"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat with {self.party.name}"

    @property
    def last_message(self):
        """Return latest message for quick access."""
        return self.messages.last()


class ChatMessage(models.Model):
    SENDER_CHOICES = (
        ("user", "User"),
        ("party", "Party"),
    )
    thread = models.ForeignKey(
        ChatThread,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    sent_by = models.CharField(max_length=10, choices=SENDER_CHOICES)
    text = models.TextField(blank=True)
    attachment = models.FileField(upload_to="chat_files/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sent_by}: {self.text[:40] if self.text else '[File]'}"

# ---------------- Orders ----------------
# MULTI PRODUCT ORDER MODELS
class Order(models.Model):
    STATUS = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("partial", "Partial"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
        ("fulfilled", "Fulfilled"),
    )

    ORDER_TYPE = (
        ("SALE", "Sale"),
        ("PURCHASE", "Purchase"),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commerce_orders",
        null=True,
        blank=True,
    )

    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="orders")

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    placed_by = models.CharField(
        max_length=10,
        choices=(("user", "User"), ("party", "Party")),
        default="party",
    )

    status = models.CharField(max_length=12, choices=STATUS, default="pending")

    # ✅ New field for distinguishing Sale / Purchase
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE, default="SALE")

    # Purchase specific fields
    invoice_number = models.CharField(max_length=50, blank=True, null=True, help_text="Purchase invoice number")
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Outstanding amount for purchase")
    payment_due_date = models.DateField(blank=True, null=True, help_text="Date when payment is due")

    notes = models.TextField(blank=True, null=True)
    bill_sundry = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    order_source = models.CharField(
        max_length=30,
        default="Manual",
        help_text="Origin of the order (e.g. Manual, WhatsApp, API).",
    )

    quotation = models.ForeignKey(
        "commerce.Quotation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        db_index=True,
        help_text="Source quotation (if this order was converted from a quotation).",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
    )

    agent = models.ForeignKey(
        FieldAgent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_orders"
    )

    DISCOUNT_TYPES = (
        ("none", "None"),
        ("percent", "Percent"),
        ("flat", "Flat"),
    )
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default="none")
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Smart BI: Festival Sale Mode (auto discounts)
    festival_campaign = models.ForeignKey(
        "smart_bi.FestivalCampaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        db_index=True,
    )
    festival_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class ConversionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIAL = "partial", "Partial"
        COMPLETED = "completed", "Completed"

    conversion_status = models.CharField(
        max_length=12,
        choices=ConversionStatus.choices,
        default=ConversionStatus.PENDING,
        db_index=True,
        help_text="Order-to-voucher conversion status.",
    )
    total_qty = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    invoiced_qty = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    def refresh_conversion_totals(self, *, save: bool = True) -> None:
        """
        Recompute total_qty/invoiced_qty and conversion_status from OrderItems.
        """
        total = Decimal("0.00")
        invoiced = Decimal("0.00")
        for it in self.items.all():
            try:
                total += Decimal(str(it.qty or 0))
            except Exception:
                pass
            try:
                invoiced += Decimal(str(getattr(it, "invoiced_qty", 0) or 0))
            except Exception:
                pass

        self.total_qty = total
        self.invoiced_qty = invoiced
        if invoiced <= Decimal("0.00"):
            self.conversion_status = Order.ConversionStatus.PENDING
        elif invoiced < total:
            self.conversion_status = Order.ConversionStatus.PARTIAL
        else:
            self.conversion_status = Order.ConversionStatus.COMPLETED

        if save:
            self.save(update_fields=["total_qty", "invoiced_qty", "conversion_status"])

    def total_amount(self):
        """Sum all order item totals with discount and tax applied."""
        agg = self.items.aggregate(
            t=models.Sum(
                models.F("qty") * models.F("price"),
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            )
        )
        subtotal = agg["t"] or Decimal("0.00")
        discount_amount = self.discount_amount or Decimal("0.00")
        festival_discount = self.festival_discount_amount or Decimal("0.00")
        tax_amount = self.tax_amount or Decimal("0.00")
        return subtotal - discount_amount - festival_discount + tax_amount + self.bill_sundry_total()

    def subtotal_amount(self):
        agg = self.items.aggregate(
            t=models.Sum(
                models.F("qty") * models.F("price"),
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            )
        )
        return agg["t"] or Decimal("0.00")

    def bill_sundry_total(self):
        total = Decimal("0.00")
        for line in (self.bill_sundry or []):
            if not isinstance(line, dict):
                continue
            try:
                total += Decimal(str(line.get("amount") or "0"))
            except Exception:
                continue
        return total

    def compute_totals(self):
        subtotal = self.items.aggregate(
            t=models.Sum(
                models.F("qty") * models.F("price"),
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            )
        )["t"] or Decimal("0.00")

        discount_amount = Decimal("0.00")
        if self.discount_type == "percent":
            discount_amount = (subtotal * (self.discount_value or Decimal("0.00"))) / Decimal("100")
        elif self.discount_type == "flat":
            discount_amount = self.discount_value or Decimal("0.00")

        if discount_amount > subtotal:
            discount_amount = subtotal

        festival_discount = self.festival_discount_amount or Decimal("0.00")
        if festival_discount < 0:
            festival_discount = Decimal("0.00")
        max_festival = subtotal - discount_amount
        if festival_discount > max_festival:
            festival_discount = max_festival if max_festival > 0 else Decimal("0.00")
            self.festival_discount_amount = festival_discount

        taxable = subtotal - discount_amount - festival_discount
        if taxable < 0:
            taxable = Decimal("0.00")
        tax_amount = (taxable * (self.tax_percent or Decimal("0.00"))) / Decimal("100")

        self.discount_amount = discount_amount
        self.tax_amount = tax_amount
        return subtotal

    def save(self, *args, **kwargs):
        # On first insert, the related manager `self.items` is not usable until we have a PK.
        # Totals are computed after items are created (see views) by calling `order.save()` again.
        if self.pk is None:
            return super().save(*args, **kwargs)

        self.compute_totals()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.pk} - {self.party.name if self.party else 'Unknown'} ({self.order_type} - {self.status})"


# ---------------- Order Item ----------------
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    qty = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    invoiced_qty = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    raw_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Raw item name when product is not matched",
    )

    def line_total(self):
        return self.qty * self.price

    def __str__(self):
        return f"{self.product.name if self.product else 'Unknown'} x {self.qty}"


# ---------------- Quotations ----------------
class Quotation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        VERIFIED = "verified", "Verified"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CONVERTED = "converted", "Converted"

    quotation_number = models.CharField(max_length=30, unique=True, null=True, blank=True, db_index=True)
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="quotations", db_index=True)
    date = models.DateField(default=timezone.localdate, db_index=True)
    valid_till = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)

    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    remarks = models.TextField(blank=True)

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotations",
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_quotations",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    converted_order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="converted_from_quotations",
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "date"], name="quote_status_date_idx"),
            models.Index(fields=["party", "status"], name="quote_party_status_idx"),
        ]

    def __str__(self):
        return self.quotation_number or f"Quotation #{self.pk}"

    @property
    def is_expired(self) -> bool:
        if not self.valid_till:
            return False
        try:
            return self.valid_till < timezone.localdate()
        except Exception:
            return False

    def _assign_number_if_missing(self):
        if self.quotation_number:
            return
        if not self.pk:
            return
        # Stable, unique and sortable-ish number (based on PK).
        # Example: QTN-202603-000012
        stamp = timezone.localdate().strftime("%Y%m")
        self.quotation_number = f"QTN-{stamp}-{int(self.pk):06d}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.quotation_number:
            self.quotation_number = None
        super().save(*args, **kwargs)
        if is_new and not self.quotation_number:
            self._assign_number_if_missing()
            if self.quotation_number:
                super().save(update_fields=["quotation_number"])


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="items", db_index=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="quotation_items", db_index=True)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotation_items",
        db_index=True,
    )

    qty = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    rate = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["quotation", "product"], name="quote_item_q_p_idx"),
        ]

    def __str__(self):
        return f"{self.product} x {self.qty}"


class QuotationAuditLog(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="audit_logs", db_index=True)
    action = models.CharField(max_length=40, db_index=True)
    from_status = models.CharField(max_length=16, blank=True, db_index=True)
    to_status = models.CharField(max_length=16, blank=True, db_index=True)
    note = models.CharField(max_length=255, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quotation_audit_logs",
        db_index=True,
    )
    performed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-performed_at", "-id"]
        indexes = [
            models.Index(fields=["quotation", "performed_at"], name="quote_audit_q_dt_idx"),
        ]


# ---------------- WhatsApp Order Inbox ----------------
class WhatsAppOrderInbox(models.Model):
    STATUS_CHOICES = (
        ("new", "New"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("manual_review", "Manual Review"),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_orders",
    )
    whatsapp_account = models.ForeignKey(
        "whatsapp.WhatsAppAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commerce_order_inbox",
        db_index=True,
    )
    party = models.ForeignKey(
        Party,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_orders",
    )
    mobile_number = models.CharField(max_length=20)
    customer_name = models.CharField(max_length=120, blank=True)
    raw_message = models.TextField()
    parsed_items = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_inbox_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"WhatsApp Order #{self.id} - {self.mobile_number}"


class WhatsAppSession(models.Model):
    STATE_CHOICES = (
        ("browsing", "Browsing"),
        ("awaiting_payment", "Awaiting Payment"),
        ("completed", "Completed"),
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_sessions",
    )
    whatsapp_account = models.ForeignKey(
        "whatsapp.WhatsAppAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commerce_sessions",
        db_index=True,
    )
    party = models.ForeignKey(
        Party,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_sessions",
    )
    mobile_number = models.CharField(max_length=20)
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default="browsing")
    selected_payment_mode = models.CharField(max_length=40, blank=True)
    unmatched_items = models.JSONField(default=list, blank=True)
    last_message_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "mobile_number"],
                condition=Q(whatsapp_account__isnull=True),
                name="uniq_wa_sess_owner_mobile_noacc",
            ),
            models.UniqueConstraint(
                fields=["owner", "whatsapp_account", "mobile_number"],
                condition=Q(whatsapp_account__isnull=False),
                name="uniq_wa_sess_owner_acc_mobile",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "whatsapp_account", "last_message_at"], name="wa_sess_owner_acc_dt_idx"),
        ]

    def __str__(self):
        return f"WhatsApp Session {self.mobile_number}"


class WhatsAppCartItem(models.Model):
    session = models.ForeignKey(
        WhatsAppSession,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ("session", "product")

    def line_total(self):
        return self.quantity * self.unit_price


# ---------------- Invoice ----------------
class Invoice(models.Model):
    STATUS = (("unpaid", "Unpaid"), ("paid", "Paid"), ("cancelled", "Cancelled"))
    GST_CHOICES = (
        ("GST", "GST"),
        ("NON_GST", "Non GST"),
    )

    gst_type = models.CharField(
        max_length=10,
        choices=GST_CHOICES,
        default="NON_GST"
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="invoice")
    number = models.CharField(max_length=32, unique=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS, default="unpaid")
    created_at = models.DateTimeField(auto_now_add=True)
    payment_link = models.URLField(blank=True, null=True)

    def save(self, *args, **kwargs):
        """Auto-generate invoice number and payment link."""
        if not self.number:
            self.number = f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # Auto-set amount from order if not given
        if not self.amount and hasattr(self, "order"):
            self.amount = self.order.total_amount()

        # Generate UPI payment link if Party has UPI ID
        party = getattr(self.order, "party", None)
        if party and party.upi_id:
            self.payment_link = (
                f"upi://pay?pa={party.upi_id}&pn={party.name.replace(' ', '%20')}"
                f"&am={self.amount}&cu=INR&tn=Invoice%20{self.number}"
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} ({self.status})"

# ---------------- Sales Voucher ----------------
class SalesVoucher(models.Model):
    invoice_no = models.AutoField(primary_key=True)

    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    party = models.ForeignKey('khataapp.Party', on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)

    is_gst = models.BooleanField(default=True)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class SalesVoucherItem(models.Model):
    voucher = models.ForeignKey(SalesVoucher, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('commerce.Product', on_delete=models.CASCADE)
    source_order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_voucher_items",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_voucher_items",
    )

    qty = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)

    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        choices=[
            (0, '0%'),
            (5, '5%'),
            (12, '12%'),
            (18, '18%'),
            (28, '28%'),
        ],
        default=0
    )


# ---------------- Payment ----------------
class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.invoice.number}: ₹{self.amount} via {self.method or 'N/A'}"


# ---------------- Payment Events (Event Bus) ----------------
from django.db.models.signals import post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_save, sender=Payment)
def _payment_event(sender, instance: "Payment", created: bool, **kwargs):
    if not created:
        return
    try:
        try:
            from smart_bi.services.fraud_detection import detect_payment_anomaly

            detect_payment_anomaly(payment=instance)
        except Exception:
            pass

        from event_bus.publish import publish_event
        try:
            from realtime.services.publisher import publish_event as publish_realtime
        except Exception:
            publish_realtime = None

        owner = None
        try:
            owner = instance.invoice.order.owner  # type: ignore[union-attr]
        except Exception:
            owner = None
        try:
            if publish_realtime and owner:
                publish_realtime(f"owner_{owner.id}", "payment.received", {"payment_id": instance.id, "amount": str(instance.amount)})
        except Exception:
            pass

        publish_event(
            topic="billing.events",
            event_type="payment.received",
            owner=owner,
            key=str(getattr(instance, "reference", "") or getattr(instance, "id", "")),
            payload={
                "payment_id": getattr(instance, "id", None),
                "invoice_id": getattr(getattr(instance, "invoice", None), "id", None),
                "amount": str(getattr(instance, "amount", "")),
                "method": getattr(instance, "method", ""),
                "reference": getattr(instance, "reference", ""),
            },
        )
    except Exception:
        return


# ---------------- Hybrid Sync Queue ----------------
class SyncQueue(models.Model):
    """
    Local-first sync queue for hybrid desktop + cloud mode.

    The desktop app writes to local SQLite first, then a background sync worker
    pushes queued actions to the configured cloud API when internet is available.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"

    device_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Desktop device ID (used to avoid ID collisions across devices).",
    )
    model_name = models.CharField(
        max_length=100,
        help_text="Django model label (recommended: app_label.ModelName).",
        db_index=True,
    )
    object_id = models.CharField(
        max_length=64,
        help_text="Local primary key value (stored as string for flexibility).",
        db_index=True,
    )
    action = models.CharField(max_length=10, choices=Action.choices, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    synced = models.BooleanField(default=False, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["synced", "-created_at"]

    def __str__(self) -> str:
        return f"{self.model_name}#{self.object_id} {self.action} (synced={self.synced})"


class SyncMapping(models.Model):
    """
    Cloud-side mapping from desktop-local IDs to cloud DB IDs.

    This enables idempotent upserts and safe foreign-key reconstruction without
    relying on matching integer primary keys between SQLite (desktop) and
    Postgres/SQLite (cloud).
    """

    device_id = models.CharField(max_length=64, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    local_id = models.CharField(max_length=64, db_index=True)
    cloud_id = models.CharField(max_length=64, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["device_id", "model_name", "local_id"],
                name="uniq_sync_mapping_device_model_local",
            )
        ]

    def __str__(self) -> str:
        return f"{self.device_id}:{self.model_name}#{self.local_id} -> {self.cloud_id}"


class SyncedObject(models.Model):
    """
    Cloud-side inbox for generic desktop sync payloads (any model/action).
    """

    device_id = models.CharField(max_length=64, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    local_id = models.CharField(max_length=64, db_index=True)
    action = models.CharField(max_length=10, choices=SyncQueue.Action.choices, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["device_id", "model_name", "local_id"],
                name="uniq_synced_object_device_model_local",
            )
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.model_name}#{self.local_id} ({self.device_id})"


class SyncedInvoice(models.Model):
    """
    Cloud-side inbox for desktop invoice sync payloads.

    This avoids hard-coupling sync to the full Order/Invoice relational graph.
    A cloud worker (or admin) can later map these payloads into the cloud schema.
    """

    number = models.CharField(max_length=32, unique=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return self.number


# ---------------- Notification ----------------
class Notification(models.Model):
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.message[:50]


# ---------------- Coupons ----------------
class Coupon(models.Model):
    COUPON_TYPES = (
        ("discount", "Discount"),
        ("offer", "Offer"),
        ("spin_win", "Spin and Win"),
        ("scratch", "Scratch Card"),
    )

    DISCOUNT_TYPES = (
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    )

    title = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    coupon_type = models.CharField(max_length=20, choices=COUPON_TYPES, default="discount")

    # Discount specific fields
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, blank=True, null=True)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Usage limits
    usage_limit = models.PositiveIntegerField(default=1)  # Total usage limit
    per_user_limit = models.PositiveIntegerField(default=1)  # Per user limit
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Validity
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # For spin-win and scratch
    win_probability = models.DecimalField(max_digits=5, decimal_places=2, default=0.1)  # 10% chance

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.code})"

    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now and
            (self.valid_until is None or self.valid_until >= now)
        )

    def get_discount_amount(self, order_total):
        if self.coupon_type != "discount":
            return Decimal("0.00")

        if self.discount_type == "percentage":
            discount = (order_total * self.discount_value) / 100
            if self.max_discount and discount > self.max_discount:
                discount = self.max_discount
        else:  # fixed
            discount = self.discount_value

        return min(discount, order_total)  # Never exceed order total


class UserCoupon(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_coupons")
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="user_coupons")
    is_used = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "coupon")

    def __str__(self):
        return f"{self.user.username} - {self.coupon.code}"


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="usages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coupon_usages")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="coupon_usages", blank=True, null=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.coupon.code} used by {self.user.username} - ₹{self.discount_amount}"


# ---------------- Stock Entry ----------------
class StockEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ("IN", "Stock In"),
        ("OUT", "Stock Out"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stockentry")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    entry_type = models.CharField(max_length=3, choices=ENTRY_TYPE_CHOICES)
    date = models.DateField()

    def __str__(self):
        return f"{self.product.name} - {self.entry_type} {self.quantity}"


# ---------------- AI Reorder Settings ----------------
class CommerceAISettings(models.Model):
    """
    Singleton-style settings for AI reorder planner thresholds.
    Admin can update these values.
    """
    fast_daily_sales = models.DecimalField(max_digits=8, decimal_places=2, default=1.50)
    medium_daily_sales = models.DecimalField(max_digits=8, decimal_places=2, default=0.60)
    slow_daily_sales = models.DecimalField(max_digits=8, decimal_places=2, default=0.20)
    safety_factor = models.DecimalField(max_digits=4, decimal_places=2, default=0.70)
    default_budget = models.DecimalField(max_digits=14, decimal_places=2, default=50000)
    default_target_days = models.PositiveIntegerField(default=30)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Commerce AI Settings"

    class Meta:
        verbose_name = "AI Reorder Setting"
        verbose_name_plural = "AI Reorder Settings"

