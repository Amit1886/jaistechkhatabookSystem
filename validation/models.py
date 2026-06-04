from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class FraudAlert(models.Model):
    class AlertType(models.TextChoices):
        DUPLICATE_INVOICE = "duplicate_invoice", "Duplicate Invoice"
        GST_MISMATCH = "gst_mismatch", "GST Mismatch"
        NEGATIVE_STOCK = "negative_stock", "Negative Stock"
        SUSPICIOUS_TXN = "suspicious_txn", "Suspicious Transaction"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        IGNORED = "ignored", "Ignored"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fraud_alerts",
        db_index=True,
    )

    alert_type = models.CharField(max_length=40, choices=AlertType.choices, db_index=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)

    reference_type = models.CharField(max_length=100, db_index=True)
    reference_id = models.PositiveBigIntegerField(db_index=True)

    title = models.CharField(max_length=160, blank=True, default="")
    message = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(blank=True, null=True, db_index=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_fraud_alerts",
    )

    class Meta:
        db_table = "validation_fraud_alerts"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "status", "created_at"], name="val_fraud_owner_st_dt_idx"),
            models.Index(fields=["owner", "alert_type", "created_at"], name="val_fraud_owner_tp_dt_idx"),
            models.Index(fields=["reference_type", "reference_id"], name="val_fraud_ref_idx"),
        ]

    def mark_resolved(self, *, by_user=None):
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.resolved_by = by_user
        self.save(update_fields=["status", "resolved_at", "resolved_by"])

    def __str__(self) -> str:
        return f"{self.alert_type} ({self.status}) {self.reference_type}#{self.reference_id}"
