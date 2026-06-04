from __future__ import annotations

import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class PortalUser(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        SUPPLIER = "supplier", "Supplier"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portal_accounts",
        db_index=True,
    )
    party = models.OneToOneField(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="portal_account",
    )
    role = models.CharField(max_length=20, choices=Role.choices, db_index=True)

    username = models.CharField(max_length=80, unique=True, db_index=True)
    password_hash = models.CharField(max_length=128)

    is_active = models.BooleanField(default=True, db_index=True)
    must_change_password = models.BooleanField(default=True)

    api_token = models.CharField(max_length=64, unique=True, blank=True, default="", db_index=True)
    api_token_created_at = models.DateTimeField(blank=True, null=True)
    api_token_last_used_at = models.DateTimeField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_portal_accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "portal_users"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "role", "is_active"], name="portal_owner_role_act_idx"),
            models.Index(fields=["owner", "created_at"], name="portal_owner_dt_idx"),
        ]

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash)

    def issue_api_token(self, *, rotate: bool = False) -> str:
        if self.api_token and not rotate:
            return self.api_token
        token = secrets.token_hex(32)
        self.api_token = token
        self.api_token_created_at = timezone.now()
        self.save(update_fields=["api_token", "api_token_created_at"])
        return token

    def save(self, *args, **kwargs):
        # Ensure unique API token is always present to avoid UNIQUE conflicts on blank default.
        if self._state.adding and not (self.api_token or "").strip():
            self.api_token = secrets.token_hex(32)
            self.api_token_created_at = timezone.now()
        super().save(*args, **kwargs)

    def touch_login(self) -> None:
        self.last_login_at = timezone.now()
        self.save(update_fields=["last_login_at"])

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"


class PortalPermission(models.Model):
    """
    Per-portal-account permissions.

    Keys (examples):
    - view_invoices
    - view_reports
    - place_orders
    - make_payments
    """

    portal_user = models.ForeignKey(
        PortalUser,
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    key = models.CharField(max_length=64, db_index=True)
    allowed = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_permissions"
        constraints = [
            models.UniqueConstraint(fields=["portal_user", "key"], name="uniq_portal_perm_user_key"),
        ]
        indexes = [
            models.Index(fields=["portal_user", "allowed"], name="portal_perm_user_allow_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.portal_user_id}:{self.key}={self.allowed}"


class PortalOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUBMITTED = "submitted", "Submitted"
        CONVERTED = "converted", "Converted"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portal_orders_owner",
        db_index=True,
    )
    portal_user = models.ForeignKey(
        PortalUser,
        on_delete=models.CASCADE,
        related_name="portal_orders",
        db_index=True,
    )
    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="portal_orders",
        db_index=True,
    )
    commerce_order = models.ForeignKey(
        "commerce.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="portal_mappings",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "portal_orders"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "status", "created_at"], name="portal_order_owner_st_dt_idx"),
            models.Index(fields=["portal_user", "created_at"], name="portal_order_user_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"PortalOrder#{self.id} {self.status}"


class CartItem(models.Model):
    portal_user = models.ForeignKey(
        PortalUser,
        on_delete=models.CASCADE,
        related_name="cart_items",
        db_index=True,
    )
    product = models.ForeignKey(
        "commerce.Product",
        on_delete=models.CASCADE,
        related_name="portal_cart_items",
        db_index=True,
    )
    qty = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cart_items"
        constraints = [
            models.UniqueConstraint(fields=["portal_user", "product"], name="uniq_portal_cart_user_product"),
        ]
        indexes = [
            models.Index(fields=["portal_user", "updated_at"], name="portal_cart_user_upd_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.portal_user_id}:{self.product_id} x{self.qty}"


class WelcomeMessageLog(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="welcome_message_logs",
        db_index=True,
    )
    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welcome_message_logs",
    )
    portal_user = models.ForeignKey(
        PortalUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="welcome_message_logs",
    )

    channel = models.CharField(max_length=20, choices=Channel.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    to = models.CharField(max_length=180, blank=True, default="")
    message_preview = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    response = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "welcome_messages_log"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "created_at"], name="wel_msg_owner_dt_idx"),
            models.Index(fields=["owner", "channel", "status"], name="wel_msg_owner_ch_st_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.channel} {self.status} to={self.to}"


class PaymentLink(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        OPENED = "opened", "Opened"
        PAID = "paid", "Paid"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_links",
        db_index=True,
    )
    invoice = models.ForeignKey(
        "commerce.Invoice",
        on_delete=models.CASCADE,
        related_name="payment_links",
        db_index=True,
    )
    portal_user = models.ForeignKey(
        PortalUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_links",
    )

    token = models.CharField(max_length=64, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    provider = models.CharField(max_length=40, blank=True, default="upi")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED, db_index=True)
    reference = models.CharField(max_length=120, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(blank=True, null=True, db_index=True)
    paid_at = models.DateTimeField(blank=True, null=True, db_index=True)
    callback_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "payment_links"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "status", "created_at"], name="paylink_owner_st_dt_idx"),
            models.Index(fields=["invoice", "status"], name="paylink_inv_st_idx"),
        ]

    def __str__(self) -> str:
        return f"PaymentLink {self.status} inv={self.invoice_id}"
