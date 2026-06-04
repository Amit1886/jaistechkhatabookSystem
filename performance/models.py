from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Target(models.Model):
    PERIOD_CHOICES = (("daily", "Daily"), ("monthly", "Monthly"))

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="performance_targets")
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default="monthly", db_index=True)
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    achieved_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    reward = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [models.Index(fields=["user", "start_date", "end_date"])]

    def progress_percent(self):
        if self.target_value == 0:
            return 0
        return min(100, (self.achieved_value / self.target_value) * 100)


class LeaderboardEntry(models.Model):
    period = models.CharField(max_length=10, default="monthly", db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leaderboard_entries")
    score = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    rank = models.PositiveIntegerField(default=0)
    computed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["period", "rank"]
        indexes = [models.Index(fields=["period", "computed_at"])]


class Reward(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="performance_rewards")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    points = models.PositiveIntegerField(default=0)
    awarded_at = models.DateTimeField(auto_now_add=True, db_index=True)

