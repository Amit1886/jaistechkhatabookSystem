from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class EventOutbox(models.Model):
    """
    Durable event outbox (for Kafka/Redis streams).

    We write events in the same DB transaction as business writes, then a background
    worker flushes pending rows to the configured bus.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbox_events",
        db_index=True,
    )

    topic = models.CharField(max_length=120, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    key = models.CharField(max_length=120, blank=True, default="", db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "event_outbox"
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="outbox_status_created_idx"),
            models.Index(fields=["topic", "created_at"], name="outbox_topic_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.topic}:{self.event_type} ({self.status})"

