from __future__ import annotations

from django.conf import settings
from django.db import models


class PaymentBehavior(models.Model):
    """
    Customer payment behavior per invoice.

    Used for:
    - Credit score calculation (timeliness + frequency)
    - Risk prediction (habitual late payers)
    - Smart reminder timing (learn typical delay)
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="smart_khata_payment_behaviors",
        db_index=True,
    )
    customer = models.ForeignKey(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="payment_behaviors",
        db_index=True,
    )
    invoice = models.OneToOneField(
        "commerce.Invoice",
        on_delete=models.CASCADE,
        related_name="payment_behavior",
        db_index=True,
    )
    due_date = models.DateField(db_index=True)
    paid_date = models.DateField(blank=True, null=True, db_index=True)
    delay_days = models.IntegerField(default=0, db_index=True, help_text="Paid late by N days (0 = on time/early)")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "customer", "-created_at"], name="skb_owner_cust_ca_idx"),
            models.Index(fields=["owner", "due_date"], name="skb_owner_due_idx"),
            models.Index(fields=["owner", "delay_days"], name="skb_owner_delay_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.customer_id} - {self.invoice_id} - delay {self.delay_days}d"

