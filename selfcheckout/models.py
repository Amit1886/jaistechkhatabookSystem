from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class CheckoutSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAYMENT_PENDING = "payment_pending", "Payment Pending"
        PAID = "paid", "Paid"
        ABANDONED = "abandoned", "Abandoned"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_sessions")
    customer = models.ForeignKey("khataapp.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="self_checkout_sessions")
    customer_mode = models.CharField(max_length=20, default="unidentified", db_index=True)
    customer_verified = models.BooleanField(default=False, db_index=True)
    customer_verified_at = models.DateTimeField(null=True, blank=True)
    guest_reference = models.CharField(max_length=60, blank=True, default="", db_index=True)
    session_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kiosk_id = models.CharField(max_length=40, default="KIOSK-1", db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    payment_method = models.CharField(max_length=30, blank=True, default="")
    payment_reference = models.CharField(max_length=100, blank=True, default="", db_index=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    invoice = models.ForeignKey("commerce.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="self_checkout_sessions")
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_activity_at = models.DateTimeField(auto_now=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    fraud_flags = models.JSONField(default=list, blank=True)
    applied_coupon = models.CharField(max_length=80, blank=True, default="")
    ai_context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "status", "last_activity_at"], name="selfco_owner_status_dt"),
            models.Index(fields=["owner", "kiosk_id", "status"], name="selfco_owner_kiosk_status"),
        ]

    def __str__(self):
        return f"{self.kiosk_id} {self.session_key}"


class CheckoutCartItem(models.Model):
    session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("commerce.Product", on_delete=models.PROTECT, related_name="self_checkout_items")
    barcode = models.CharField(max_length=80, blank=True, default="")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "product"], name="uniq_selfco_session_product"),
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="selfco_item_qty_positive"),
        ]
        ordering = ["id"]

    @property
    def line_total(self):
        return max((self.quantity * self.unit_price) - self.discount, Decimal("0.00"))


class KioskDevice(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        BUSY = "busy", "Busy"
        OFFLINE = "offline", "Offline"
        MAINTENANCE = "maintenance", "Maintenance"

    kiosk_id = models.CharField(max_length=40, unique=True, db_index=True)
    name = models.CharField(max_length=120, blank=True, default="")
    zone = models.CharField(max_length=80, blank=True, default="Front Checkout")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ONLINE, db_index=True)
    scanner_status = models.CharField(max_length=20, default="online")
    printer_status = models.CharField(max_length=20, default="ready")
    payment_status = models.CharField(max_length=20, default="online")
    internet_status = models.CharField(max_length=20, default="online")
    camera_status = models.CharField(max_length=20, default="ready")
    cpu_usage = models.PositiveSmallIntegerField(default=18)
    memory_usage = models.PositiveSmallIntegerField(default=34)
    avg_checkout_seconds = models.PositiveIntegerField(default=165)
    current_session = models.ForeignKey(CheckoutSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_kiosks")
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    diagnostics = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["kiosk_id"]

    def __str__(self):
        return self.name or self.kiosk_id


class QueueTicket(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        ASSIGNED = "assigned", "Assigned"
        SERVED = "served", "Served"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_queue")
    ticket_code = models.CharField(max_length=24, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING, db_index=True)
    assigned_kiosk = models.ForeignKey(KioskDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="queue_tickets")
    estimated_wait_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["owner", "status", "created_at"], name="selfco_queue_owner_status")]

    def __str__(self):
        return self.ticket_code


class KioskEvent(models.Model):
    class EventType(models.TextChoices):
        SCAN = "scan", "Scan"
        RFID = "rfid", "RFID"
        VOICE = "voice", "Voice"
        COUPON = "coupon", "Coupon"
        PAYMENT = "payment", "Payment"
        FRAUD = "fraud", "Fraud"
        HEALTH = "health", "Health"
        ASSISTANT = "assistant", "Assistant"
        CUSTOMER = "customer", "Customer"
        SUPPORT = "support", "Support"
        THEME = "theme", "Theme"
        IDLE = "idle", "Idle"

    session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, null=True, blank=True, related_name="events")
    kiosk = models.ForeignKey(KioskDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices, db_index=True)
    message = models.CharField(max_length=255, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    severity = models.CharField(max_length=20, default="info", db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["event_type", "created_at"], name="selfco_event_type_dt")]

    def __str__(self):
        return f"{self.event_type}: {self.message[:60]}"


class CustomerMembership(models.Model):
    party = models.OneToOneField("khataapp.Party", on_delete=models.CASCADE, related_name="self_checkout_membership")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_memberships")
    member_code = models.CharField(max_length=32, unique=True, db_index=True)
    qr_token = models.CharField(max_length=80, unique=True, db_index=True)
    nfc_uid = models.CharField(max_length=80, null=True, blank=True, unique=True, db_index=True)
    face_hash = models.CharField(max_length=128, blank=True, default="", db_index=True)
    tier = models.CharField(max_length=30, default="Silver", db_index=True)
    wallet_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    welcome_coupon = models.CharField(max_length=40, blank=True, default="")
    welcome_awarded = models.BooleanField(default=False)
    consent_face = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_seen_at", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "tier"], name="selfco_mem_owner_tier"),
            models.Index(fields=["owner", "is_blocked"], name="selfco_mem_owner_blocked"),
        ]

    def __str__(self):
        return f"{self.member_code} - {self.party}"


class CustomerOTPChallenge(models.Model):
    class Purpose(models.TextChoices):
        EXISTING = "existing", "Existing Customer"
        ONBOARD = "onboard", "New Customer"

    session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="otp_challenges")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_otps")
    mobile = models.CharField(max_length=15, db_index=True)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.EXISTING, db_index=True)
    code = models.CharField(max_length=8)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_verified = models.BooleanField(default=False, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "mobile", "is_verified"], name="selfco_otp_owner_mobile")]

    def __str__(self):
        return f"{self.mobile} {self.purpose}"


class SupportRequest(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        RESOLVED = "resolved", "Resolved"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        URGENT = "urgent", "Urgent"
        EMERGENCY = "emergency", "Emergency"

    session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="support_requests")
    kiosk = models.ForeignKey(KioskDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="support_requests")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_support_requests")
    issue_type = models.CharField(max_length=60, default="general_help", db_index=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    customer_name = models.CharField(max_length=120, blank=True, default="")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_self_checkout_support")
    opened_at = models.DateTimeField(default=timezone.now, db_index=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-opened_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "status", "opened_at"], name="selfco_support_owner_status"),
            models.Index(fields=["kiosk", "status"], name="selfco_support_kiosk_status"),
        ]

    def __str__(self):
        return f"{self.kiosk.kiosk_id if self.kiosk_id else 'Kiosk'} {self.issue_type} {self.status}"


class KioskInteractionEvent(models.Model):
    class EventKind(models.TextChoices):
        CLICK = "click", "Click"
        TOUCH = "touch", "Touch"
        HOVER = "hover", "Hover"
        ADD = "add", "Add To Cart"
        ABANDON = "abandon", "Abandonment"

    session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="interaction_events")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_interactions")
    product = models.ForeignKey("commerce.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="self_checkout_interactions")
    kiosk_id = models.CharField(max_length=40, db_index=True)
    kind = models.CharField(max_length=20, choices=EventKind.choices, db_index=True)
    area = models.CharField(max_length=80, db_index=True)
    x = models.PositiveSmallIntegerField(default=0)
    y = models.PositiveSmallIntegerField(default=0)
    intensity = models.PositiveSmallIntegerField(default=1)
    duration_ms = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "kiosk_id", "created_at"], name="selfco_ix_owner_kiosk_dt"),
            models.Index(fields=["kind", "area", "created_at"], name="selfco_ix_kind_area_dt"),
        ]

    def __str__(self):
        return f"{self.kind} {self.area} {self.intensity}"


class MobileContinueSession(models.Model):
    session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="mobile_continue_sessions")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_mobile_sessions")
    token = models.CharField(max_length=80, unique=True, db_index=True)
    device_label = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "is_active", "expires_at"], name="selfco_mob_owner_active_exp")]

    def __str__(self):
        return f"{self.session.kiosk_id} mobile handoff"


class RewardCampaign(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_reward_campaigns")
    coupon_code = models.CharField(max_length=40, default="LUCKY25")
    cashback_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("25.00"))
    probability = models.PositiveSmallIntegerField(default=35)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name


class RewardDrop(models.Model):
    session = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="reward_drops")
    campaign = models.ForeignKey(RewardCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="drops")
    reward_type = models.CharField(max_length=30, default="coupon", db_index=True)
    title = models.CharField(max_length=120)
    coupon_code = models.CharField(max_length=40, blank=True, default="")
    cashback_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class PromoMedia(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_promo_media")
    title = models.CharField(max_length=140)
    media_url = models.URLField(blank=True, default="")
    product = models.ForeignKey("commerce.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="self_checkout_promo_media")
    badge = models.CharField(max_length=40, blank=True, default="Flash Sale")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    def __str__(self):
        return self.title


class RetailBroadcast(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        EMERGENCY = "emergency", "Emergency"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_broadcasts")
    title = models.CharField(max_length=140)
    message = models.CharField(max_length=280)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL, db_index=True)
    voice_enabled = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "is_active", "priority"], name="selfco_bcast_owner_active")]

    def __str__(self):
        return f"{self.priority}: {self.title}"


class RetailSyncSnapshot(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="self_checkout_sync_snapshots")
    key = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        unique_together = ("owner", "key")
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} v{self.version}"
