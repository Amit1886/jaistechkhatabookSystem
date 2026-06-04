from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        FACEBOOK = "facebook", "Facebook Ads"
        INSTAGRAM = "instagram", "Instagram Ads"
        GOOGLE = "google", "Google Ads"
        OTT = "ott", "OTT Ads"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns_created",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    name = models.CharField(max_length=140)
    audience = models.JSONField(default=dict, blank=True, help_text="Filter definition for audience selection.")
    ai_prompt = models.TextField(blank=True, default="")
    ad_copy = models.TextField(blank=True, default="")
    ai_creative_url = models.URLField(blank=True, default="")
    language = models.CharField(max_length=16, default="auto", help_text="auto / hi / en / hi-en")
    pincodes = models.JSONField(default=list, blank=True, help_text="Hyperlocal targeting (list of pincodes)")
    budget_daily = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    optimize_goal = models.CharField(max_length=40, blank=True, default="", help_text="cpa / ctr / conversions")
    metadata = models.JSONField(default=dict, blank=True)

    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    recipients_total = models.PositiveIntegerField(default=0)
    recipients_sent = models.PositiveIntegerField(default=0)
    recipients_failed = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "status", "scheduled_at"])]

    def mark_running(self):
        if self.status != self.Status.RUNNING:
            self.status = self.Status.RUNNING
            self.started_at = timezone.now()
            self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def mark_failed(self, error: str):
        self.status = self.Status.FAILED
        self.last_error = (error or "")[:2000]
        self.save(update_fields=["status", "last_error", "updated_at"])

    def __str__(self) -> str:
        return f"{self.name} ({self.channel})"


class QRCode(models.Model):
    class Kind(models.TextChoices):
        AGENT = "agent", "Agent QR"
        CAMPAIGN = "campaign", "Campaign QR"
        PRODUCT = "product", "Product QR"

    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="marketing_qrcodes")
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name="qrcodes")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.CAMPAIGN, db_index=True)
    target_url = models.URLField(blank=True, default="")
    scan_count = models.IntegerField(default=0)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "created_at"], name="qr_kind_dt_idx"),
            models.Index(fields=["agent", "created_at"], name="qr_agent_dt_idx"),
        ]

    def bump_scan(self):
        from django.utils import timezone

        self.scan_count += 1
        self.last_scanned_at = timezone.now()
        self.save(update_fields=["scan_count", "last_scanned_at", "updated_at"])


class CampaignMessage(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="messages")
    lead = models.ForeignKey("leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="campaign_messages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaign_messages")

    destination = models.CharField(max_length=120, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider_ref = models.CharField(max_length=120, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["campaign", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]


class CreativeAsset(models.Model):
    """
    Lightweight creative registry for vendor marketing:
    - IMAGE: uses product image URL
    - REEL: uses product video URL (if uploaded)

    Phase A: Stores references only (no video rendering server-side).
    Phase B: Can be extended to generate reels/templates via workers.
    """

    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        REEL = "reel", "Reel/Video"
        GIF = "gif", "Reel GIF"

    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="creative_assets")
    product = models.ForeignKey("products.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="creative_assets")
    kind = models.CharField(max_length=20, choices=Kind.choices, db_index=True, default=Kind.IMAGE)
    title = models.CharField(max_length=160, blank=True, default="")
    caption = models.TextField(blank=True, default="")
    file = models.FileField(upload_to="creative_assets/", blank=True, null=True)
    source_url = models.URLField(blank=True, default="")
    template = models.CharField(max_length=60, blank=True, default="", help_text="Template name for future rendering.")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["vendor", "kind", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.vendor_id}:{self.kind}:{self.title or self.product_id or self.id}"

    @property
    def asset_url(self) -> str:
        try:
            if self.file and hasattr(self.file, "url"):
                return str(self.file.url)
        except Exception:
            pass
        return self.source_url or "/static/images/placeholder.png"


class PaidAdRun(models.Model):
    """
    Stores paid ads runs for Campaigns (Facebook/Instagram/Google/OTT).

    Phase A (demo):
    - We simulate execution locally and store metrics.
    Phase B:
    - Connect to provider APIs and store real status + insights.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="paid_runs")
    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.CASCADE, related_name="paid_ad_runs")
    channel = models.CharField(max_length=20, choices=Campaign.Channel.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)

    budget_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)

    provider_ref = models.CharField(max_length=140, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    queued_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-queued_at"]
        indexes = [
            models.Index(fields=["vendor", "status", "queued_at"]),
            models.Index(fields=["channel", "status", "queued_at"]),
        ]

    def mark_running(self):
        if self.status != self.Status.RUNNING:
            self.status = self.Status.RUNNING
            self.started_at = timezone.now()
            self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def mark_failed(self, error: str):
        self.status = self.Status.FAILED
        self.last_error = (error or "")[:2000]
        self.save(update_fields=["status", "last_error", "updated_at"])
