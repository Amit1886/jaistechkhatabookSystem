from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AgentCustomerAssignment(models.Model):
    """
    Assignment history for Customer -> Agent mapping.

    We keep history rows so reassignments don't lose earning/commission context.
    """

    company = models.ForeignKey(
        "core_settings.CompanySettings",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agent_customer_assignments",
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_assignments",
        db_index=True,
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_assignments",
        db_index=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_created",
    )
    assigned_at = models.DateTimeField(default=timezone.now, db_index=True)
    unassigned_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reason = models.CharField(max_length=200, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-assigned_at", "-id"]
        indexes = [
            models.Index(fields=["company", "customer", "unassigned_at"]),
            models.Index(fields=["company", "agent", "unassigned_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "customer"],
                condition=Q(unassigned_at__isnull=True),
                name="uniq_active_assignment_per_customer_company",
            )
        ]

    @property
    def is_active(self) -> bool:
        return self.unassigned_at is None

    def __str__(self) -> str:
        return f"{self.customer_id} -> {self.agent_id} (active={self.is_active})"

