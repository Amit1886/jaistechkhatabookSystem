from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class AIInsight(models.Model):
    """
    Cached insights for dashboards/widgets.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_insights",
        db_index=True,
    )
    key = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "ai_insights"
        constraints = [
            models.UniqueConstraint(fields=["owner", "key"], name="uniq_ai_insight_owner_key"),
        ]
        indexes = [
            models.Index(fields=["owner", "computed_at"], name="aiins_owner_dt_idx"),
        ]
        ordering = ["-computed_at", "-id"]

    def __str__(self) -> str:
        return f"{self.key} ({self.computed_at:%Y-%m-%d})"

