from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Lead(models.Model):
    class Source(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        GOOGLE = "google", "Google"
        WEBSITE = "website", "Website"
        REFERRAL = "referral", "Referral"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        NEW = "new", "New"
        HOT = "hot", "Hot"
        WARM = "warm", "Warm"
        COLD = "cold", "Cold"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        INACTIVE = "inactive", "Inactive"

    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="leads",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_created",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_assigned",
        db_index=True,
    )

    name = models.CharField(max_length=160, blank=True, default="")
    mobile = models.CharField(max_length=20, blank=True, default="", db_index=True)
    email = models.EmailField(blank=True, default="")

    source = models.CharField(max_length=30, choices=Source.choices, default=Source.MANUAL, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    score = models.IntegerField(default=0, db_index=True)

    pincode_text = models.CharField(max_length=12, blank=True, default="")
    pincode = models.ForeignKey(
        "location.Pincode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    metadata = models.JSONField(default=dict, blank=True)

    next_followup_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status", "created_at"]),
            models.Index(fields=["company", "assigned_to", "status"]),
            models.Index(fields=["mobile"]),
        ]

    def touch_contacted(self):
        self.last_contacted_at = timezone.now()
        self.save(update_fields=["last_contacted_at", "updated_at"])

    def __str__(self) -> str:
        return f"{self.name or self.mobile} ({self.status})"


class LeadActivity(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    activity_type = models.CharField(max_length=40, default="note", db_index=True)
    note = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["lead", "created_at"])]

