from __future__ import annotations

from django.conf import settings
from django.db import models


class WhatsAppSession(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        QR_REQUIRED = "qr_required", "QR Required"
        CONNECTED = "connected", "Connected"
        DISCONNECTED = "disconnected", "Disconnected"
        ERROR = "error", "Error"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wa_sessions",
        db_index=True,
    )
    session_id = models.CharField(max_length=120, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    qr_payload = models.TextField(blank=True, default="")
    last_qr_at = models.DateTimeField(blank=True, null=True)
    last_connected_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, default="")
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.session_id} ({self.status})"


class TemplateMessage(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wa_templates",
        db_index=True,
    )
    name = models.SlugField(max_length=80, db_index=True)
    text = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("owner", "name")

    def __str__(self) -> str:
        return self.name


class MessageLog(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="wa_message_logs",
        db_index=True,
    )
    session_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    direction = models.CharField(max_length=10, choices=Direction.choices, db_index=True)
    phone = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=120, blank=True, default="")
    message = models.TextField(blank=True, default="")
    message_type = models.CharField(max_length=24, blank=True, default="", db_index=True)
    provider_message_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, blank=True, default="", db_index=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.direction} {self.phone}"

