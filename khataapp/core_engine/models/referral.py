from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class ReferralRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made",
        db_index=True,
    )
    referred = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_received",
        db_index=True,
    )

    commission_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        db_table = "referral_records"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["referrer", "referred"], name="uniq_referrer_referred"),
        ]
        indexes = [
            models.Index(fields=["referrer", "status", "created_at"], name="ref_ref_st_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"Referral {self.referrer_id}->{self.referred_id} ({self.status})"

