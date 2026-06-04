from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Sum
from django.db.models import Avg
from django.utils import timezone

from khataapp.models import Transaction
from ledger.models import StockLedger


@dataclass(frozen=True)
class SuspiciousTxn:
    ok: bool
    message: str = ""
    score: float = 0.0


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def detect_suspicious_transaction(txn: Transaction) -> SuspiciousTxn:
    """
    Best-effort:
    - flag if amount is > 3x recent average for same party.
    """
    if not txn:
        return SuspiciousTxn(ok=True)
    party = getattr(txn, "party", None)
    if not party:
        return SuspiciousTxn(ok=True)

    amount = _to_decimal(getattr(txn, "amount", None))
    if amount <= 0:
        return SuspiciousTxn(ok=True)

    since = (getattr(txn, "created_at", None) or timezone.now()) - timedelta(days=30)
    avg_amount = (
        Transaction.objects.filter(party=party, created_at__gte=since)
        .exclude(id=txn.id)
        .aggregate(a=Avg("amount"))
        .get("a")
    )
    avg_amount_d = _to_decimal(avg_amount or 0)
    if avg_amount_d <= 0:
        return SuspiciousTxn(ok=True)

    if amount > avg_amount_d * Decimal("3"):
        return SuspiciousTxn(ok=False, message="Transaction amount is unusually high vs last 30 days average.", score=0.85)
    return SuspiciousTxn(ok=True)


def find_negative_stock(owner, *, product_ids: list[int]) -> list[dict]:
    """
    Detect products where (IN - OUT) < 0 based on ledger.StockLedger.
    """
    if not owner or not product_ids:
        return []

    rows = (
        StockLedger.objects.filter(owner=owner, product_id__in=product_ids)
        .values("product_id", "product__name")
        .annotate(total_in=Sum("quantity_in"), total_out=Sum("quantity_out"))
    )

    out: list[dict] = []
    for r in rows:
        total_in = _to_decimal(r.get("total_in") or 0)
        total_out = _to_decimal(r.get("total_out") or 0)
        balance = total_in - total_out
        if balance < 0:
            out.append(
                {
                    "product_id": r.get("product_id"),
                    "product": r.get("product__name") or "Unknown",
                    "balance": float(balance),
                }
            )
    return out
