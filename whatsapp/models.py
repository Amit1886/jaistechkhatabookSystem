from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from whatsapp.fields import EncryptedTextField


class WhatsAppAccount(models.Model):
    class Provider(models.TextChoices):
        META_CLOUD_API = "meta_cloud_api", "WhatsApp Cloud API (Official)"
        WEB_GATEWAY = "web_gateway", "WhatsApp Web / QR Gateway"

    class Status(models.TextChoices):
        DISCONNECTED = "disconnected", "Disconnected"
        CONNECTING = "connecting", "Connecting"
        CONNECTED = "connected", "Connected"
        ERROR = "error", "Error"
        DISABLED = "disabled", "Disabled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_accounts",
        db_index=True,
    )

    label = models.CharField(max_length=120, blank=True, default="")
    phone_number = models.CharField(max_length=32, blank=True, default="", db_index=True)

    provider = models.CharField(max_length=30, choices=Provider.choices, default=Provider.META_CLOUD_API, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DISCONNECTED, db_index=True)
    last_seen_at = models.DateTimeField(blank=True, null=True)

    # ---------------- Meta Cloud API (Official) ----------------
    meta_phone_number_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    meta_waba_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    meta_graph_version = models.CharField(max_length=16, blank=True, default="v20.0")
    meta_access_token = EncryptedTextField(blank=True, default="")
    meta_app_secret = EncryptedTextField(blank=True, default="")
    meta_verify_token = models.CharField(max_length=80, blank=True, default="", db_index=True)

    # ---------------- Web Gateway (QR / Session based) ----------------
    gateway_base_url = models.CharField(max_length=255, blank=True, default="")
    gateway_api_key = EncryptedTextField(blank=True, default="")
    gateway_session_id = models.CharField(max_length=120, blank=True, default="", db_index=True)

    # Optional per-account shared secret for non-Meta inbound webhooks/gateways.
    webhook_secret = EncryptedTextField(blank=True, default="")

    # ---------------- Quick Commerce (Blinkit-style) ----------------
    quick_commerce_enabled = models.BooleanField(default=False, db_index=True)
    quick_delivery_radius_km = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    store_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    store_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    quick_assign_agent = models.ForeignKey(
        "khataapp.FieldAgent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_quick_accounts",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_accounts"
        ordering = ["-created_at", "-updated_at"]
        indexes = [
            models.Index(fields=["owner", "provider", "status"], name="wa_acc_owner_pr_st_idx"),
            models.Index(fields=["provider", "status"], name="wa_acc_pr_st_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "phone_number"],
                condition=~Q(phone_number=""),
                name="uniq_wa_account_owner_phone",
            ),
            models.UniqueConstraint(
                fields=["meta_phone_number_id"],
                condition=~Q(meta_phone_number_id=""),
                name="uniq_wa_meta_phone_number_id",
            ),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.provider == self.Provider.META_CLOUD_API and not (self.meta_verify_token or "").strip():
                self.meta_verify_token = uuid.uuid4().hex
            if not (self.webhook_secret or "").strip():
                # Used for non-Meta gateways posting into our platform.
                self.webhook_secret = uuid.uuid4().hex + uuid.uuid4().hex
        super().save(*args, **kwargs)

    def touch_seen(self) -> None:
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at", "updated_at"])

    def __str__(self) -> str:
        label = self.label or (self.phone_number or str(self.id))
        return f"{label} ({self.provider})"


class WhatsAppSession(models.Model):
    """
    Connection session (primarily for QR / Web-Gateway connectors).

    Note: Commerce chat/cart state is stored separately in `commerce.WhatsAppSession`.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        QR_REQUIRED = "qr_required", "QR Required"
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(WhatsAppAccount, on_delete=models.CASCADE, related_name="sessions", db_index=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    provider_session_id = models.CharField(max_length=160, blank=True, default="", db_index=True)
    qr_payload = models.TextField(blank=True, default="")

    last_qr_at = models.DateTimeField(blank=True, null=True)
    last_connected_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, default="")

    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_sessions"
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["account", "status"], name="wa_sess_acc_st_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.account_id} ({self.status})"


class Customer(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_customers",
        db_index=True,
    )
    whatsapp_account = models.ForeignKey(
        WhatsAppAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
        db_index=True,
    )

    phone_number = models.CharField(max_length=32, db_index=True)
    display_name = models.CharField(max_length=120, blank=True, default="")

    party = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_customers",
    )

    tags = models.JSONField(default=list, blank=True)

    # ---------------- Visual Flow Builder (state) ----------------
    active_visual_flow = models.ForeignKey(
        "whatsapp.VisualFlow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    visual_flow_node_id = models.CharField(max_length=80, blank=True, default="", db_index=True)
    visual_flow_updated_at = models.DateTimeField(blank=True, null=True)

    last_seen_at = models.DateTimeField(blank=True, null=True)
    last_location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_location_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_customers"
        ordering = ["-updated_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "phone_number"],
                condition=Q(whatsapp_account__isnull=True),
                name="uniq_wa_customer_owner_phone_noacc",
            ),
            models.UniqueConstraint(
                fields=["owner", "whatsapp_account", "phone_number"],
                condition=Q(whatsapp_account__isnull=False),
                name="uniq_wa_customer_owner_acc_phone",
            ),
        ]
        indexes = [
            models.Index(fields=["owner", "phone_number"], name="wa_cust_owner_phone_idx"),
        ]

    def touch_seen(self) -> None:
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at", "updated_at"])

    def __str__(self) -> str:
        return f"{self.display_name or self.phone_number}"


class WhatsAppOperator(models.Model):
    """
    Phone numbers allowed to operate the ERP via WhatsApp messages (admin/staff commands).

    Example use cases:
    - "sales today"
    - "low stock"
    - "sale 5 item 250"
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_operators",
        db_index=True,
    )
    whatsapp_account = models.ForeignKey(
        WhatsAppAccount,
        on_delete=models.CASCADE,
        related_name="operators",
        db_index=True,
    )

    phone_number = models.CharField(max_length=32, db_index=True)
    display_name = models.CharField(max_length=120, blank=True, default="")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.ADMIN, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_operators"
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["whatsapp_account", "is_active", "updated_at"], name="wa_op_acc_act_dt_idx"),
            models.Index(fields=["owner", "is_active", "updated_at"], name="wa_op_owner_act_dt_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["whatsapp_account", "phone_number"], name="uniq_wa_op_acc_phone"),
        ]

    def __str__(self) -> str:
        label = (self.display_name or self.phone_number).strip()
        return f"{label} ({self.role})"


class Bot(models.Model):
    class Kind(models.TextChoices):
        WELCOME = "welcome", "Welcome Bot"
        ORDER = "order", "Order Bot"
        PAYMENT = "payment", "Payment Bot"
        SUPPORT = "support", "Support Bot"
        LEAD = "lead", "Lead Generation Bot"
        APPOINTMENT = "appointment", "Appointment Booking Bot"
        SURVEY = "survey", "Survey Bot"
        CUSTOM = "custom", "Custom Bot"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_bots",
        db_index=True,
    )
    whatsapp_account = models.OneToOneField(
        WhatsAppAccount,
        on_delete=models.CASCADE,
        related_name="bot",
        db_index=True,
    )

    name = models.CharField(max_length=120, default="WhatsApp Bot")
    kind = models.CharField(max_length=30, choices=Kind.choices, default=Kind.ORDER, db_index=True)

    is_enabled = models.BooleanField(default=True, db_index=True)
    auto_reply_enabled = models.BooleanField(default=True, db_index=True)
    ai_fallback_enabled = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_bots"
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "kind", "is_enabled"], name="wa_bot_owner_kind_en_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


class BotMessage(models.Model):
    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"
        LOCATION = "location", "Location"
        CONTACT = "contact", "Contact"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="messages", db_index=True)

    key = models.SlugField(max_length=80, db_index=True)
    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT, db_index=True)

    text = models.TextField(blank=True, default="")
    media_url = models.URLField(blank=True, default="")
    filename = models.CharField(max_length=120, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_bot_messages"
        constraints = [
            models.UniqueConstraint(fields=["bot", "key"], name="uniq_wa_bot_msg_key"),
        ]
        indexes = [
            models.Index(fields=["bot", "message_type"], name="wa_bot_msg_bot_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.bot_id}:{self.key}"


class BotFlow(models.Model):
    class TriggerType(models.TextChoices):
        KEYWORD = "keyword", "Keyword"
        MENU_SELECTION = "menu_selection", "Menu Selection"
        BUTTON_CLICK = "button_click", "Button Click"
        CART_ACTION = "cart_action", "Cart Action"
        PAYMENT_CONFIRMATION = "payment_confirmation", "Payment Confirmation"
        ORDER_STATUS = "order_status", "Order Status"
        BROADCAST_TRIGGER = "broadcast_trigger", "Broadcast Trigger"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="flows", db_index=True)

    name = models.CharField(max_length=140)
    description = models.TextField(blank=True, default="")

    trigger_type = models.CharField(max_length=40, choices=TriggerType.choices, db_index=True)
    trigger_value = models.CharField(max_length=140, blank=True, default="", db_index=True)
    trigger_payload = models.JSONField(default=dict, blank=True)

    # List of actions in order; each action is a dict, example:
    # {"type":"send_text","text":"Hello"}
    actions = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(default=100, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_bot_flows"
        ordering = ["priority", "-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["bot", "is_active", "priority"], name="wa_flow_bot_act_pr_idx"),
            models.Index(fields=["bot", "trigger_type", "trigger_value"], name="wa_flow_bot_trig_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.bot_id}:{self.name}"


class BotTemplate(models.Model):
    """
    Admin-managed global template library.

    payload schema (example):
    {
      "messages": [{"key":"welcome","message_type":"text","text":"Hi!"}],
      "flows": [{"name":"Welcome","trigger_type":"keyword","trigger_value":"hi","actions":[{"type":"send_message_key","key":"welcome"}]}]
    }
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Null = admin-managed global template. Set = tenant/user-owned reusable template.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_bot_templates",
        db_index=True,
    )

    name = models.CharField(max_length=140, db_index=True)
    kind = models.CharField(max_length=30, choices=Bot.Kind.choices, default=Bot.Kind.ORDER, db_index=True)
    description = models.TextField(blank=True, default="")

    payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_bot_templates"
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["is_active", "kind", "updated_at"], name="wa_tpl_act_kind_dt_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class BroadcastCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class TargetType(models.TextChoices):
        ALL_CUSTOMERS = "all_customers", "All Customers"
        SELECTED_CUSTOMERS = "selected_customers", "Selected Customers"
        CUSTOMER_TAG = "customer_tag", "Customer Tag"
        RECENT_BUYERS = "recent_buyers", "Recent Buyers"
        INACTIVE_CUSTOMERS = "inactive_customers", "Inactive Customers"

    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_broadcasts",
        db_index=True,
    )
    whatsapp_account = models.ForeignKey(
        WhatsAppAccount,
        on_delete=models.CASCADE,
        related_name="broadcasts",
        db_index=True,
    )

    name = models.CharField(max_length=140, default="Broadcast Campaign")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    target_type = models.CharField(max_length=40, choices=TargetType.choices, default=TargetType.ALL_CUSTOMERS, db_index=True)
    target_payload = models.JSONField(default=dict, blank=True)

    message_type = models.CharField(max_length=20, choices=MessageType.choices, default=MessageType.TEXT, db_index=True)
    text = models.TextField(blank=True, default="")
    media_url = models.URLField(blank=True, default="")

    scheduled_at = models.DateTimeField(blank=True, null=True, db_index=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    stats = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_broadcast_campaigns"
        ordering = ["-created_at", "-updated_at"]
        indexes = [
            models.Index(fields=["owner", "status", "scheduled_at"], name="wa_bc_owner_st_sched_idx"),
            models.Index(fields=["whatsapp_account", "status"], name="wa_bc_acc_st_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.status})"


class WhatsAppMessage(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "in", "Inbound"
        OUTBOUND = "out", "Outbound"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"
        IGNORED = "ignored", "Ignored"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_messages",
        db_index=True,
    )

    whatsapp_account = models.ForeignKey(
        WhatsAppAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="message_logs",
        db_index=True,
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="message_logs",
        db_index=True,
    )

    direction = models.CharField(max_length=8, choices=Direction.choices, db_index=True)
    from_number = models.CharField(max_length=32, blank=True, default="")
    to_number = models.CharField(max_length=32, blank=True, default="")
    body = EncryptedTextField(blank=True, default="")
    message_type = models.CharField(max_length=24, blank=True, default="", db_index=True)
    provider_message_id = models.CharField(max_length=120, blank=True, default="")

    parsed_intent = models.CharField(max_length=64, blank=True, default="", db_index=True)
    parsed_payload = models.JSONField(default=dict, blank=True)

    reference_type = models.CharField(max_length=100, blank=True, default="", db_index=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)

    raw_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "whatsapp_messages"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "created_at"], name="wa_msg_owner_dt_idx"),
            models.Index(fields=["owner", "status", "created_at"], name="wa_msg_owner_st_dt_idx"),
            models.Index(fields=["whatsapp_account", "created_at"], name="wa_msg_acc_dt_idx"),
            models.Index(fields=["provider_message_id"], name="wa_msg_provider_id_idx"),
        ]

    def __str__(self) -> str:
        direction = "IN" if self.direction == self.Direction.INBOUND else "OUT"
        return f"[{direction}] {self.from_number}->{self.to_number} ({self.status})"


class MessageLog(WhatsAppMessage):
    class Meta:
        proxy = True
        verbose_name = "Message Log"
        verbose_name_plural = "Message Logs"


class VisualFlow(models.Model):
    """
    WhatsApp user-side visual bot flow (drag & drop builder).

    Designed to be multi-tenant: scoped to (owner, whatsapp_account).
    """

    class NodeType(models.TextChoices):
        START = "start", "Start"
        MESSAGE = "message", "Message"
        CONDITION = "condition", "Condition"
        ACTION = "action", "Action"
        END = "end", "End"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="whatsapp_visual_flows",
        db_index=True,
    )
    whatsapp_account = models.ForeignKey(
        WhatsAppAccount,
        on_delete=models.CASCADE,
        related_name="visual_flows",
        db_index=True,
    )

    name = models.CharField(max_length=140, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "whatsapp_visual_flows"
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["whatsapp_account", "is_active", "updated_at"], name="wa_vf_acc_act_dt_idx"),
            models.Index(fields=["owner", "updated_at"], name="wa_vf_owner_dt_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["whatsapp_account", "name"], name="uniq_wa_vf_acc_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.whatsapp_account_id})"


class VisualNode(models.Model):
    flow = models.ForeignKey(VisualFlow, on_delete=models.CASCADE, related_name="nodes", db_index=True)
    node_id = models.CharField(max_length=80)
    node_type = models.CharField(max_length=20, choices=VisualFlow.NodeType.choices, db_index=True)
    data = models.JSONField(default=dict, blank=True)
    position_x = models.IntegerField(default=40)
    position_y = models.IntegerField(default=40)

    class Meta:
        db_table = "whatsapp_visual_nodes"
        constraints = [
            models.UniqueConstraint(fields=["flow", "node_id"], name="uniq_wa_vnode_flow_nodeid"),
        ]
        indexes = [
            models.Index(fields=["flow", "node_type"], name="wa_vnode_flow_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.flow_id}:{self.node_type}:{self.node_id}"


class VisualEdge(models.Model):
    flow = models.ForeignKey(VisualFlow, on_delete=models.CASCADE, related_name="edges", db_index=True)
    source_id = models.CharField(max_length=80, db_index=True)
    target_id = models.CharField(max_length=80, db_index=True)
    condition_text = models.CharField(max_length=200, blank=True, default="")
    is_default = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "whatsapp_visual_edges"
        indexes = [
            models.Index(fields=["flow", "source_id"], name="wa_vedge_flow_src_idx"),
            models.Index(fields=["flow", "is_default"], name="wa_vedge_flow_def_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.flow_id}:{self.source_id}->{self.target_id}"
