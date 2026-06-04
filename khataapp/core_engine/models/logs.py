from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class EngineEventLog(models.Model):
    class Category(models.TextChoices):
        FLOW = "flow", "Flow"
        AUDIT = "audit", "Audit"

    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARN = "warn", "Warn"
        ERROR = "error", "Error"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="engine_event_logs",
        db_index=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="engine_actor_logs",
    )

    category = models.CharField(max_length=10, choices=Category.choices, default=Category.FLOW, db_index=True)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO, db_index=True)
    event_key = models.CharField(max_length=80, db_index=True, blank=True, default="")
    message = models.TextField(blank=True, default="")
    meta = models.JSONField(default=dict, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=64, blank=True, default="")
    content_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "engine_event_logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "category", "created_at"], name="englog_owner_cat_dt_idx"),
            models.Index(fields=["owner", "level", "created_at"], name="englog_owner_lvl_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.category}:{self.level} {self.event_key}".strip()


class RewardLedgerEntry(models.Model):
    class Source(models.TextChoices):
        INVOICE = "invoice", "Invoice"
        PAYMENT = "payment", "Payment"
        REFERRAL = "referral", "Referral"
        TASK = "task", "Daily Task"
        LOYALTY = "loyalty", "Loyalty"
        STORAGE = "storage", "Storage"
        MANUAL = "manual", "Manual"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reward_ledger_entries",
        db_index=True,
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL, db_index=True)

    coins_delta = models.BigIntegerField(default=0)
    points_delta = models.BigIntegerField(default=0)
    amount_reference = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    meta = models.JSONField(default=dict, blank=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=64, blank=True, default="")
    content_object = GenericForeignKey("content_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "reward_ledger_entries"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "source", "created_at"], name="rew_owner_src_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"Reward {self.source} coins={self.coins_delta} points={self.points_delta}"

