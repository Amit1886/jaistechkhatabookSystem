from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class FraudSignal(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        IGNORED = "ignored", "Ignored"

    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fraud_signals",
    )
    signal_type = models.CharField(max_length=60, db_index=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.LOW, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="fraud_signals")
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fraud_signals_related",
    )
    description = models.CharField(max_length=300, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    detected_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fraud_signals_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["company", "signal_type", "status"]),
            models.Index(fields=["user", "detected_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.signal_type}:{self.severity}:{self.status}"

