from __future__ import annotations

import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class BusinessGrowthEngine(models.Model):
    """
    Central per-user growth state.

    This model is designed to be stable and future-proof: other engine models
    append detailed ledgers/logs, while this table holds the user-facing totals
    and cached snapshot data used by dashboards.
    """

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_growth_engine",
        db_index=True,
    )

    # Rewards
    total_rewards = models.PositiveBigIntegerField(default=0, help_text="Total reward coins earned (lifetime).")
    reward_points = models.PositiveBigIntegerField(default=0, help_text="Total reward points (lifetime).")

    # Earnings
    referral_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    payment_commission_earned = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    # Credits / meters
    whatsapp_credits = models.PositiveIntegerField(default=0)
    loyalty_points = models.PositiveBigIntegerField(default=0)
    daily_task_streak = models.PositiveIntegerField(default=0)
    level = models.PositiveIntegerField(default=1)

    last_reward_update = models.DateTimeField(blank=True, null=True)

    # Plan/feature gates (cached for UI)
    plan_locked_features = models.JSONField(default=list, blank=True)

    # Storage tracking (bytes)
    storage_used = models.BigIntegerField(default=0)

    # Cached analytics payload used by dashboards
    analytics_snapshot = models.JSONField(default=dict, blank=True)

    # Profit protection configuration snapshot (JSON)
    admin_profit_formula = models.JSONField(default=dict, blank=True)

    # Referral discovery
    referral_code = models.CharField(max_length=24, unique=True, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "business_growth_engine"
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "-updated_at"], name="bge_owner_upd_idx"),
        ]

    def __str__(self) -> str:
        return f"BusinessGrowthEngine(owner={self.owner_id})"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            # Short, URL-safe, unique-enough referral code.
            self.referral_code = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:16]
        super().save(*args, **kwargs)

    def touch_rewards(self):
        self.last_reward_update = timezone.now()
        self.save(update_fields=["last_reward_update", "updated_at"])

