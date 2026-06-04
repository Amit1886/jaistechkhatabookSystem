from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class DailyTaskDefinition(models.Model):
    key = models.CharField(max_length=60, unique=True, db_index=True)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    coins_reward = models.PositiveIntegerField(default=0)
    points_reward = models.PositiveIntegerField(default=0)
    cashback_reward = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "daily_task_definitions"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.title


class DailyTaskCompletion(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_task_completions",
        db_index=True,
    )
    task = models.ForeignKey(
        DailyTaskDefinition,
        on_delete=models.CASCADE,
        related_name="completions",
    )
    day = models.DateField(db_index=True)
    completed_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "daily_task_completions"
        ordering = ["-day", "-completed_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "task", "day"], name="uniq_daily_task_owner_task_day"),
        ]
        indexes = [
            models.Index(fields=["owner", "day"], name="dtc_owner_day_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.owner_id} {self.task_id} {self.day}"

