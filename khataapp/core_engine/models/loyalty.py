from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models


class LoyaltyAccount(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_accounts",
        db_index=True,
    )
    party = models.OneToOneField(
        "khataapp.Party",
        on_delete=models.CASCADE,
        related_name="loyalty_account",
    )

    points = models.BigIntegerField(default=0)
    cashback_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "loyalty_accounts"
        indexes = [
            models.Index(fields=["owner", "-updated_at"], name="loy_owner_upd_idx"),
        ]

    def __str__(self) -> str:
        return f"LoyaltyAccount(party={self.party_id})"


class LoyaltyLedgerEntry(models.Model):
    class Source(models.TextChoices):
        TRANSACTION = "transaction", "Transaction"
        INVOICE = "invoice", "Invoice"
        MANUAL = "manual", "Manual"

    account = models.ForeignKey(
        LoyaltyAccount,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty_ledger_entries",
        db_index=True,
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL, db_index=True)

    points_delta = models.BigIntegerField(default=0)
    cashback_delta = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "loyalty_ledger_entries"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["owner", "source", "created_at"], name="loy_owner_src_dt_idx"),
        ]

    def __str__(self) -> str:
        return f"Loyalty {self.source} points={self.points_delta} cashback={self.cashback_delta}"

