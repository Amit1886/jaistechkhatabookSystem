from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    full_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CustomerProfile({self.user_id})"


class CustomerAddress(models.Model):
    profile = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=60, default="Home")
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    pincode = models.CharField(max_length=10, db_index=True)
    district = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    alternate_mobile = models.CharField(max_length=15, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["profile", "is_default"])]

    def __str__(self):
        return f"{self.profile_id}:{self.label}"


class VendorProductListing(models.Model):
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="listings")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="vendor_listings")
    is_online = models.BooleanField(default=False, db_index=True)
    title = models.CharField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"), db_index=True)
    rating_count = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("vendor", "product")
        indexes = [
            models.Index(fields=["vendor", "is_online"]),
            models.Index(fields=["vendor", "is_featured"]),
        ]

    @property
    def effective_title(self) -> str:
        return (self.title or "").strip() or self.product.name

    @property
    def effective_description(self) -> str:
        return (self.description or "").strip() or (getattr(self.product, "description", "") or "").strip()

    @property
    def effective_price(self) -> Decimal:
        if self.price_override is not None:
            return Decimal(str(self.price_override))
        return Decimal(str(getattr(self.product, "b2c_price", "0") or "0"))

    def __str__(self):
        return f"{self.vendor_id}:{self.product_id}"


class VendorCoupon(models.Model):
    """
    Vendor-scoped enablement for coupons created in billing/commerce.

    We reuse `commerce.Coupon` but let each vendor decide which codes are active in their store.
    """

    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="vendor_coupons")
    coupon = models.ForeignKey("commerce.Coupon", on_delete=models.CASCADE, related_name="vendor_coupons")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vendor", "coupon")
        indexes = [models.Index(fields=["vendor", "is_active"])]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.coupon_id}:{'active' if self.is_active else 'off'}"


class Wishlist(models.Model):
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="wishlists")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlists")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vendor", "customer")

    def __str__(self):
        return f"{self.vendor_id}:{self.customer_id}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(VendorProductListing, on_delete=models.CASCADE, related_name="wishlisted_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("wishlist", "listing")


class Cart(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONVERTED = "converted", "Converted"
        ABANDONED = "abandoned", "Abandoned"

    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="carts")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["vendor", "customer", "status"])]

    def __str__(self):
        return f"{self.vendor_id}:{self.customer_id}:{self.status}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(VendorProductListing, on_delete=models.CASCADE, related_name="cart_items")
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("cart", "listing")
        indexes = [models.Index(fields=["cart", "listing"])]

    @property
    def line_total(self) -> Decimal:
        return Decimal(str(self.unit_price)) * Decimal(int(self.qty))


def _generate_order_number() -> str:
    return f"SO-{timezone.now().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


class StoreOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        PACKED = "packed", "Packed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        INITIATED = "initiated", "Initiated"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="orders")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="store_orders")
    address = models.ForeignKey(CustomerAddress, on_delete=models.SET_NULL, null=True, blank=True)

    public_token = models.UUIDField(default=uuid4, unique=True, db_index=True, editable=False)
    order_number = models.CharField(max_length=40, unique=True, db_index=True, default=_generate_order_number)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True
    )

    subtotal_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    shipping_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    applied_coupon = models.ForeignKey(
        "commerce.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="store_orders",
        help_text="Applied coupon code (from billing/commerce) at checkout time.",
    )
    referrer_code = models.CharField(max_length=24, blank=True, default="")
    referral_reward_processed = models.BooleanField(default=False, db_index=True)

    billing_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_store_orders",
        help_text="Internal ERP order created on vendor acceptance.",
    )
    commerce_order = models.OneToOneField(
        "commerce.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="storefront_order",
        help_text="Centralized billing order (commerce) for ledger/voucher flow.",
    )

    invoice_pdf = models.FileField(upload_to="store_invoices/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["vendor", "status", "created_at"]),
            models.Index(fields=["vendor", "payment_status", "created_at"]),
            models.Index(fields=["customer", "created_at"]),
        ]

    def recalc_totals(self, *, save: bool = True):
        subtotal = Decimal("0.00")
        for item in self.items.all():
            subtotal += item.line_total
        self.subtotal_amount = subtotal
        self.tax_amount = Decimal("0.00")
        self.total_amount = (self.subtotal_amount + self.tax_amount + self.shipping_amount) - self.discount_amount
        if save:
            self.save(
                update_fields=[
                    "subtotal_amount",
                    "tax_amount",
                    "total_amount",
                    "shipping_amount",
                    "discount_amount",
                    "updated_at",
                ]
            )

    @transaction.atomic
    def accept_and_create_erp_order(self, *, warehouse=None):
        if self.status != StoreOrder.Status.PENDING:
            return self.billing_order

        from orders.models import Order as ERPOrder, OrderItem as ERPOrderItem

        warehouse = warehouse or self.vendor.primary_warehouse
        erp_order = ERPOrder.objects.filter(order_number=self.order_number).first()
        if not erp_order:
            erp_order = ERPOrder.objects.create(
                order_number=self.order_number,
                order_type=ERPOrder.OrderType.ONLINE,
                customer=self.customer,
                warehouse=warehouse,
                status=ERPOrder.Status.PENDING,
                subtotal=self.subtotal_amount,
                tax_amount=self.tax_amount,
                discount_amount=self.discount_amount,
                total_amount=self.total_amount,
            )
        for item in self.items.select_related("product").all():
            ERPOrderItem.objects.create(
                order=erp_order,
                product=item.product,
                qty=item.qty,
                unit_price=item.unit_price,
                tax_percent=Decimal("0.00"),
                line_discount=Decimal("0.00"),
                line_total=item.line_total,
                margin_total=Decimal("0.00"),
            )

        self.status = StoreOrder.Status.ACCEPTED
        self.billing_order = erp_order
        self.save(update_fields=["status", "billing_order", "updated_at"])
        StoreOrderStatusEvent.objects.create(order=self, status=self.status, note="Accepted by vendor")
        return erp_order

    def __str__(self):
        return self.order_number


class StoreOrderItem(models.Model):
    order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(VendorProductListing, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["order", "product"])]

    @property
    def line_total(self) -> Decimal:
        return Decimal(str(self.unit_price)) * Decimal(int(self.qty))


class StoreOrderStatusEvent(models.Model):
    order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name="status_events")
    status = models.CharField(max_length=20, choices=StoreOrder.Status.choices, db_index=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["order", "created_at"])]


class StorePaymentAttempt(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name="payment_attempts")
    provider = models.CharField(max_length=30, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    external_ref = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StoreShipment(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PICKUP_REQUESTED = "pickup_requested", "Pickup requested"
        IN_TRANSIT = "in_transit", "In transit"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    order = models.OneToOneField(StoreOrder, on_delete=models.CASCADE, related_name="shipment")
    provider = models.CharField(max_length=30, db_index=True)
    tracking_number = models.CharField(max_length=80, blank=True, db_index=True)
    external_ref = models.CharField(max_length=120, blank=True, db_index=True, help_text="Provider shipment/order id.")
    courier_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.CREATED, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    last_tracked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PlatformSettings(models.Model):
    """
    Marketplace-wide settings (commission + settlement).
    Keep as a singleton (first row).
    """

    platform_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_settings",
        help_text="Wallet owner user for platform commission credits (e.g., Superadmin).",
    )
    commission_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PlatformSettings({self.commission_percent}%)"


class StoreSettlement(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SETTLED = "settled", "Settled"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    order = models.OneToOneField("storefront.StoreOrder", on_delete=models.CASCADE, related_name="settlement")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    commission_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    commission_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    vendor_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    vendor_wallet_txn_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    platform_wallet_txn_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    error = models.CharField(max_length=255, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

class StoreWebhookDelivery(models.Model):
    """
    Provider webhook delivery audit + idempotency guard.

    `dedupe_key` is computed from raw request body (sha256) to safely ignore retries/duplicates.
    """

    provider = models.CharField(max_length=30, db_index=True)
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="webhook_deliveries")
    dedupe_key = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=20, default="received", db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ("provider", "vendor", "dedupe_key")
        indexes = [models.Index(fields=["provider", "vendor", "created_at"])]
