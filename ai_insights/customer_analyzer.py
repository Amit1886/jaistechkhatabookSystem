from __future__ import annotations

from decimal import Decimal

from django.db.models import F, Q
from django.db.models import Sum
from django.db.models.functions import Coalesce

from khataapp.models import Party


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def compute_customer_outstanding(owner, *, limit: int = 10) -> list[dict]:
    """
    Best-effort outstanding:
    - invoice total (sales) - payments against invoice.
    """
    limit = max(5, min(int(limit or 10), 50))
    qs = (
        Party.objects.filter(owner=owner, party_type="customer")
        .annotate(
            inv_total=Coalesce(
                Sum("orders__invoice__amount", filter=Q(orders__order_type="SALE")),
                Decimal("0.00"),
            ),
            paid_total=Coalesce(
                Sum("orders__invoice__payments__amount", filter=Q(orders__order_type="SALE")),
                Decimal("0.00"),
            ),
        )
        .annotate(outstanding=F("inv_total") - F("paid_total"))
        .filter(outstanding__gt=0)
        .order_by("-outstanding")[:limit]
    )
    return [{"party_id": p.id, "party": p.name, "outstanding": float(_to_decimal(p.outstanding))} for p in qs]
