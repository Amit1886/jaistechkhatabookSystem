from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="crm_profile")
    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="crm_customers",
    )
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    lifecycle_stage = models.CharField(max_length=50, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.user_id}:{self.lifecycle_stage}"


class CustomerNote(models.Model):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class CallLog(models.Model):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="call_logs")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    direction = models.CharField(max_length=10, choices=(("outbound", "Outbound"), ("inbound", "Inbound")))
    duration_seconds = models.PositiveIntegerField(default=0)
    outcome = models.CharField(max_length=80, blank=True, default="")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class FollowUp(models.Model):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="followups")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=160)
    due_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def mark_done(self):
        if not self.completed_at:
            self.completed_at = timezone.now()
            self.save(update_fields=["completed_at"])


class LocalShop(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        DEMO = "demo", "Demo given"
        CONVERTED = "converted", "Converted"
        LOST = "lost", "Lost"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="local_shops")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="local_shops_assigned")
    company = models.ForeignKey("core_settings.CompanySettings", on_delete=models.CASCADE, null=True, blank=True, related_name="local_shops")

    shop_name = models.CharField(max_length=180)
    owner_name = models.CharField(max_length=160, blank=True, default="")
    mobile = models.CharField(max_length=20, db_index=True)
    category = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    referral_code = models.CharField(max_length=40, blank=True, default="")

    metadata = models.JSONField(default=dict, blank=True)
    trial_expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status", "created_at"], name="ls_owner_status_idx"),
            models.Index(fields=["agent", "status"], name="ls_agent_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.shop_name} ({self.mobile})"
