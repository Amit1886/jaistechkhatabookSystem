import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Branch(models.Model):
    class BranchType(models.TextChoices):
        STORE = "store", "Store"
        DARK_STORE = "dark_store", "Dark store"
        WAREHOUSE = "warehouse", "Warehouse"
        KIOSK = "kiosk", "Kiosk"

    name = models.CharField(max_length=140)
    code = models.CharField(max_length=40, unique=True)
    branch_type = models.CharField(max_length=20, choices=BranchType.choices, default=BranchType.STORE, db_index=True)
    warehouse = models.ForeignKey("warehouse.Warehouse", on_delete=models.SET_NULL, null=True, blank=True, related_name="retail_branches")
    address = models.TextField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_retail_branches")
    is_active = models.BooleanField(default=True, db_index=True)
    is_locked = models.BooleanField(default=False, db_index=True)
    emergency_mode = models.BooleanField(default=False, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["branch_type", "is_active"]),
            models.Index(fields=["warehouse", "is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class BranchUser(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        PACKER = "packer", "Packer"
        RIDER = "rider", "Rider"
        ANALYST = "analyst", "Analyst"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="users")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="retail_branch_roles")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CASHIER, db_index=True)
    can_override_price = models.BooleanField(default=False)
    can_remote_control = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("branch", "user", "role")
        indexes = [models.Index(fields=["branch", "role", "is_active"])]

    def __str__(self):
        return f"{self.branch_id}:{self.user_id}:{self.role}"


class BranchInventory(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="inventories")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="branch_inventories")
    available_qty = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    shelf_qty = models.IntegerField(default=0)
    reorder_point = models.PositiveIntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    last_stock_sync_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "product")
        indexes = [
            models.Index(fields=["branch", "available_qty"]),
            models.Index(fields=["product", "expiry_date"]),
        ]

    @property
    def sellable_qty(self):
        return self.available_qty - self.reserved_qty


class BranchTransfer(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REQUESTED = "requested", "Requested"
        IN_TRANSIT = "in_transit", "In transit"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    transfer_no = models.CharField(max_length=50, unique=True)
    source_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="outgoing_transfers")
    destination_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="incoming_transfers")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="requested_branch_transfers")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_branch_transfers")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["source_branch", "status"]), models.Index(fields=["destination_branch", "status"])]


class BranchAnalytics(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="analytics_snapshots")
    snapshot_date = models.DateField(default=timezone.localdate, db_index=True)
    sales_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gross_margin = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    order_count = models.PositiveIntegerField(default=0)
    average_bill_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    stockout_count = models.PositiveIntegerField(default=0)
    customer_count = models.PositiveIntegerField(default=0)
    staff_activity_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("branch", "snapshot_date")
        indexes = [models.Index(fields=["snapshot_date", "sales_total"])]


class PricingRule(models.Model):
    class ConditionType(models.TextChoices):
        STOCK_LOW = "stock_low", "Stock low"
        EXPIRY_NEAR = "expiry_near", "Expiry near"
        FESTIVAL = "festival", "Festival"
        SLOW_SELLING = "slow_selling", "Slow selling"
        PEAK_HOUR = "peak_hour", "Peak hour"
        VIP_CUSTOMER = "vip_customer", "VIP customer"
        BULK_QTY = "bulk_qty", "Bulk quantity"
        BRANCH = "branch", "Branch specific"
        HAPPY_HOUR = "happy_hour", "Happy hour"
        AI_RECOMMENDED = "ai_recommended", "AI recommended"

    class AdjustmentType(models.TextChoices):
        PERCENT = "percent", "Percent"
        FIXED = "fixed", "Fixed amount"
        SET_PRICE = "set_price", "Set price"

    name = models.CharField(max_length=160)
    condition_type = models.CharField(max_length=30, choices=ConditionType.choices, db_index=True)
    adjustment_type = models.CharField(max_length=20, choices=AdjustmentType.choices, default=AdjustmentType.PERCENT)
    adjustment_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    priority = models.PositiveIntegerField(default=100, db_index=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name="pricing_rules")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, null=True, blank=True, related_name="retail_pricing_rules")
    category = models.ForeignKey("products.Category", on_delete=models.CASCADE, null=True, blank=True, related_name="retail_pricing_rules")
    min_qty = models.PositiveIntegerField(default=1)
    stock_threshold = models.PositiveIntegerField(default=0)
    expiry_days_threshold = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
    time_window_start = models.TimeField(null=True, blank=True)
    time_window_end = models.TimeField(null=True, blank=True)
    customer_segment = models.CharField(max_length=60, blank=True, db_index=True)
    offer_tag = models.CharField(max_length=80, blank=True)
    conditions = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active", "priority"]),
            models.Index(fields=["condition_type", "is_active"]),
            models.Index(fields=["branch", "product", "is_active"]),
        ]

    def __str__(self):
        return self.name


class OfferCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        PAUSED = "paused", "Paused"
        ENDED = "ended", "Ended"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=160)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    branches = models.ManyToManyField(Branch, blank=True, related_name="offer_campaigns")
    products = models.ManyToManyField("products.Product", blank=True, related_name="offer_campaigns")
    categories = models.ManyToManyField("products.Category", blank=True, related_name="offer_campaigns")
    discount_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    badge_text = models.CharField(max_length=80, blank=True)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    auto_apply = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "starts_at", "ends_at"])]


class FestivalCampaign(models.Model):
    name = models.CharField(max_length=160)
    festival_name = models.CharField(max_length=120)
    offer_campaign = models.ForeignKey(OfferCampaign, on_delete=models.CASCADE, related_name="festival_modes")
    animation_theme = models.CharField(max_length=80, blank=True)
    qr_coupon_code = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ComboOffer(models.Model):
    name = models.CharField(max_length=160)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name="combo_offers")
    products = models.ManyToManyField("products.Product", related_name="combo_offers")
    combo_price = models.DecimalField(max_digits=12, decimal_places=2)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BranchPrice(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="branch_prices")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="branch_prices")
    price = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    offer_tag = models.CharField(max_length=80, blank=True)
    is_live_override = models.BooleanField(default=False, db_index=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "product")
        indexes = [models.Index(fields=["branch", "product", "is_live_override"])]


class DynamicPriceLog(models.Model):
    rule = models.ForeignKey(PricingRule, on_delete=models.SET_NULL, null=True, blank=True, related_name="price_logs")
    campaign = models.ForeignKey(OfferCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="price_logs")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey("products.Product", on_delete=models.SET_NULL, null=True, blank=True)
    old_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    new_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    margin_percent = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    reason = models.CharField(max_length=160, blank=True)
    event_payload = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["branch", "product", "created_at"])]


class RetailScreen(models.Model):
    class Orientation(models.TextChoices):
        HORIZONTAL = "horizontal", "Horizontal TV"
        VERTICAL = "vertical", "Vertical TV"
        KIOSK = "kiosk", "Kiosk"
        COUNTER = "counter", "Counter display"

    name = models.CharField(max_length=140)
    device_uid = models.CharField(max_length=80, unique=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="screens")
    orientation = models.CharField(max_length=20, choices=Orientation.choices, default=Orientation.HORIZONTAL)
    pairing_token = models.CharField(max_length=80, blank=True, db_index=True)
    is_online = models.BooleanField(default=False, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pairing_token:
            self.pairing_token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)


class MediaAsset(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        GIF = "gif", "GIF"
        HTML = "html", "HTML slide"

    title = models.CharField(max_length=160)
    media_type = models.CharField(max_length=20, choices=MediaType.choices, db_index=True)
    file = models.FileField(upload_to="retail_os/signage/", null=True, blank=True)
    html_content = models.TextField(blank=True)
    duration_seconds = models.PositiveIntegerField(default=10)
    audio_enabled = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CampaignPlaylist(models.Model):
    name = models.CharField(max_length=160)
    screens = models.ManyToManyField(RetailScreen, blank=True, related_name="playlists")
    branches = models.ManyToManyField(Branch, blank=True, related_name="screen_playlists")
    assets = models.ManyToManyField(MediaAsset, through="CampaignPlaylistItem", related_name="playlists")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(default=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CampaignPlaylistItem(models.Model):
    playlist = models.ForeignKey(CampaignPlaylist, on_delete=models.CASCADE, related_name="items")
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name="playlist_items")
    sort_order = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        unique_together = ("playlist", "asset", "sort_order")


class LiveAnnouncement(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        OFFER = "offer", "Offer"
        WARNING = "warning", "Warning"
        EMERGENCY = "emergency", "Emergency"

    title = models.CharField(max_length=160)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO, db_index=True)
    branches = models.ManyToManyField(Branch, blank=True, related_name="live_announcements")
    screens = models.ManyToManyField(RetailScreen, blank=True, related_name="live_announcements")
    fullscreen = models.BooleanField(default=False)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BranchScreenMapping(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="screen_mappings")
    screen = models.ForeignKey(RetailScreen, on_delete=models.CASCADE, related_name="branch_mappings")
    zone_name = models.CharField(max_length=80, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("branch", "screen")


class IoTDevice(models.Model):
    class DeviceType(models.TextChoices):
        SCALE = "scale", "Weighing machine"
        THERMAL_PRINTER = "thermal_printer", "Thermal printer"
        BARCODE_SCANNER = "barcode_scanner", "Barcode scanner"
        NFC_READER = "nfc_reader", "NFC reader"
        RFID_READER = "rfid_reader", "RFID reader"
        SMART_SHELF = "smart_shelf", "Smart shelf"
        CAMERA = "camera", "Camera analytics"
        ATTENDANCE = "attendance", "Attendance device"
        TOKEN_DISPLAY = "token_display", "Token display"
        BILLING_DISPLAY = "billing_display", "Billing display"

    class ConnectionType(models.TextChoices):
        USB = "usb", "USB"
        SERIAL = "serial", "Serial"
        BLUETOOTH = "bluetooth", "Bluetooth"
        WIFI = "wifi", "WiFi"
        NETWORK = "network", "Network"

    name = models.CharField(max_length=140)
    device_uid = models.CharField(max_length=100, unique=True)
    device_type = models.CharField(max_length=30, choices=DeviceType.choices, db_index=True)
    connection_type = models.CharField(max_length=20, choices=ConnectionType.choices, default=ConnectionType.USB)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="iot_devices")
    auth_token_hash = models.CharField(max_length=128, blank=True)
    firmware_version = models.CharField(max_length=60, blank=True)
    config = models.JSONField(default=dict, blank=True)
    capabilities = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_online = models.BooleanField(default=False, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["device_type", "is_online"]), models.Index(fields=["branch", "is_active"])]


class DeviceAssignment(models.Model):
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE, related_name="assignments")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="device_assignments")
    terminal = models.ForeignKey("pos.POSTerminal", on_delete=models.SET_NULL, null=True, blank=True, related_name="iot_assignments")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    purpose = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DeviceHealth(models.Model):
    device = models.OneToOneField(IoTDevice, on_delete=models.CASCADE, related_name="health")
    status = models.CharField(max_length=30, default="unknown", db_index=True)
    battery_percent = models.PositiveIntegerField(null=True, blank=True)
    signal_strength = models.IntegerField(null=True, blank=True)
    error_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeviceLog(models.Model):
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE, related_name="logs")
    level = models.CharField(max_length=20, default="info", db_index=True)
    message = models.CharField(max_length=255)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class DeviceEvent(models.Model):
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=80, db_index=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey("products.Product", on_delete=models.SET_NULL, null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class DarkStoreInventory(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="dark_store_inventory")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="dark_store_inventory")
    available_qty = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0)
    pick_zone = models.CharField(max_length=80, blank=True)
    bin_code = models.CharField(max_length=80, blank=True)
    max_eta_minutes = models.PositiveIntegerField(default=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "product")
        indexes = [models.Index(fields=["branch", "available_qty"]), models.Index(fields=["pick_zone", "bin_code"])]


class QuickCommerceOrder(models.Model):
    class Status(models.TextChoices):
        PLACED = "placed", "Placed"
        ACCEPTED = "accepted", "Accepted"
        PACKING = "packing", "Packing"
        PACKED = "packed", "Packed"
        RIDER_ASSIGNED = "rider_assigned", "Rider assigned"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="quick_commerce")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="quick_orders")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PLACED, db_index=True)
    promised_eta_minutes = models.PositiveIntegerField(default=10)
    packing_started_at = models.DateTimeField(null=True, blank=True)
    packed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_otp = models.CharField(max_length=8, blank=True)
    route_payload = models.JSONField(default=dict, blank=True)
    proof_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["branch", "status", "created_at"])]


class PackingTask(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PICKING = "picking", "Picking"
        VERIFIED = "verified", "Verified"
        PACKED = "packed", "Packed"
        EXCEPTION = "exception", "Exception"

    quick_order = models.ForeignKey(QuickCommerceOrder, on_delete=models.CASCADE, related_name="packing_tasks")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    qty = models.PositiveIntegerField()
    barcode_verified = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=100, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RiderProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rider_profile")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="riders")
    is_available = models.BooleanField(default=True, db_index=True)
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    active_order_count = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("5.00"))
    last_seen_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)


class DeliveryAllocation(models.Model):
    quick_order = models.OneToOneField(QuickCommerceOrder, on_delete=models.CASCADE, related_name="delivery_allocation")
    rider = models.ForeignKey(RiderProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="allocations")
    allocation_score = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    eta_minutes = models.PositiveIntegerField(default=10)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=30, default="allocated", db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RetailAuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["action", "created_at"]), models.Index(fields=["branch", "created_at"])]
