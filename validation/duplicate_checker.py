from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from commerce.models import Invoice


def find_potential_duplicate_invoice(invoice: Invoice) -> Optional[Invoice]:
    """
    Best-effort duplicate detection:
    - same owner
    - same party (order.party)
    - similar amount
    - created within short window
    """
    if not invoice or not getattr(invoice, "order_id", None):
        return None
    owner = getattr(getattr(invoice, "order", None), "owner", None)
    party_id = getattr(getattr(invoice, "order", None), "party_id", None)
    if not owner or not party_id:
        return None

    amount = getattr(invoice, "amount", None) or Decimal("0.00")
    # within 5 minutes
    dt_from = (getattr(invoice, "created_at", None) or timezone.now()) - timedelta(minutes=5)
    dt_to = (getattr(invoice, "created_at", None) or timezone.now()) + timedelta(minutes=5)

    qs = (
        Invoice.objects.filter(order__owner=owner, order__party_id=party_id)
        .exclude(id=invoice.id)
        .filter(created_at__gte=dt_from, created_at__lte=dt_to)
    )
    # amount within 1%
    low = amount * Decimal("0.99")
    high = amount * Decimal("1.01")
    qs = qs.filter(amount__gte=low, amount__lte=high)
    return qs.order_by("-created_at").first()

