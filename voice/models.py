from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class VoiceCommand(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PARSED = "parsed", "Parsed"
        CREATED = "created", "Entry Created"
        FAILED = "failed", "Failed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_commands",
        db_index=True,
    )
    raw_text = models.TextField(blank=True, default="")
    parsed_intent = models.CharField(max_length=64, blank=True, default="", db_index=True)
    parsed_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    error = models.TextField(blank=True, default="")

    reference_type = models.CharField(max_length=100, blank=True, default="", db_index=True)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "voice_commands"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "created_at"], name="vc_owner_dt_idx"),
            models.Index(fields=["owner", "status", "created_at"], name="vc_owner_st_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"VoiceCommand #{self.id} ({self.status})"


class VoiceCall(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DIALING = "dialing", "Dialing"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Trigger(models.TextChoices):
        NEW_LEAD = "new_lead", "New Lead"
        INACTIVE_LEAD = "inactive_lead", "Lead Inactive"
        MANUAL = "manual", "Manual"

    lead = models.ForeignKey("leads.Lead", on_delete=models.CASCADE, related_name="voice_calls")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="voice_calls")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.NEW_LEAD, db_index=True)

    language = models.CharField(max_length=12, default="auto", help_text="auto / hi / en / hi-en")
    script_prompt = models.TextField(blank=True, default="", help_text="System prompt used for TTS/LLM generation")
    response_text = models.TextField(blank=True, default="")
    summary = models.TextField(blank=True, default="")
    recording_url = models.URLField(blank=True, default="")
    provider = models.CharField(max_length=20, blank=True, default="twilio")
    provider_call_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    last_error = models.TextField(blank=True, default="")

    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lead", "status", "created_at"], name="vc_lead_status_idx"),
            models.Index(fields=["agent", "created_at"], name="vc_agent_dt_idx"),
        ]

    def mark_started(self):
        if not self.started_at:
            self.started_at = timezone.now()
            self.status = self.Status.DIALING
            self.save(update_fields=["started_at", "status", "updated_at"])

    def mark_completed(self, *, summary: str = "", recording_url: str = ""):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if summary:
            self.summary = summary[:2000]
        if recording_url:
            self.recording_url = recording_url
        self.save(update_fields=["status", "completed_at", "summary", "recording_url", "updated_at"])

    def mark_failed(self, error: str):
        self.status = self.Status.FAILED
        self.last_error = (error or "")[:2000]
        self.save(update_fields=["status", "last_error", "updated_at"])
