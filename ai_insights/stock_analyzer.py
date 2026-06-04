from __future__ import annotations

from django.db.models import F
from django.db.models import Sum
from django.utils import timezone
import math
from datetime import timedelta

from commerce.models import OrderItem, Product


def compute_low_stock(owner, *, limit: int = 10) -> list[dict]:
    limit = max(5, min(int(limit or 10), 50))
    qs = (
        Product.objects.filter(owner=owner)
        .filter(stock__lte=F("min_stock"))
        .order_by("stock", "name")[:limit]
    )
    return [{"id": p.id, "name": p.name, "stock": int(p.stock or 0), "min_stock": int(p.min_stock or 0)} for p in qs]


def compute_reorder_suggestions(
    owner,
    *,
    days: int = 30,
    target_days_of_stock: int = 14,
    alert_days_left: int = 7,
    limit: int = 10,
) -> list[dict]:
    """
    Predict products that may need reordering soon (simple, explainable heuristic).

    - Looks at last `days` sales quantity per product.
    - Estimates average daily sales.
    - Computes days of stock left and a suggested reorder quantity to reach `target_days_of_stock`.

    This avoids heavy ML dependencies and works offline.
    """
    days = max(7, min(int(days or 30), 180))
    limit = max(5, min(int(limit or 10), 50))
    target_days_of_stock = max(3, min(int(target_days_of_stock or 14), 60))
    alert_days_left = max(1, min(int(alert_days_left or 7), 30))

    start = timezone.now() - timedelta(days=days)

    # Aggregate sold qty per product (owner-scoped)
    sold = (
        OrderItem.objects.filter(order__owner=owner, order__order_type="SALE")
        .exclude(order__status__in=["cancelled", "rejected"])
        .filter(order__created_at__gte=start)
        .values("product_id")
        .annotate(qty=Sum("qty"))
    )
    sold_map = {row["product_id"]: int(row["qty"] or 0) for row in sold if row.get("product_id")}

    if not sold_map:
        return []

    out: list[dict] = []
    products = Product.objects.filter(owner=owner, id__in=list(sold_map.keys())).only("id", "name", "stock", "min_stock")
    for p in products:
        sold_qty = int(sold_map.get(p.id) or 0)
        if sold_qty <= 0:
            continue
        avg_daily = float(sold_qty) / float(days)
        if avg_daily <= 0:
            continue

        stock = int(p.stock or 0)
        days_left = (float(stock) / avg_daily) if avg_daily > 0 else 9999.0
        desired_stock = int(math.ceil(avg_daily * float(target_days_of_stock)))
        reorder_qty = max(0, desired_stock - stock)

        # Alert if stock is low vs min_stock OR predicted days left below threshold
        if stock <= int(p.min_stock or 0) or days_left <= float(alert_days_left):
            out.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "stock": stock,
                    "min_stock": int(p.min_stock or 0),
                    "sold_qty": sold_qty,
                    "avg_daily": round(avg_daily, 2),
                    "days_left": round(days_left, 1),
                    "suggest_reorder_qty": int(reorder_qty),
                }
            )

    out.sort(key=lambda r: (r.get("days_left", 9999), -int(r.get("sold_qty", 0))))
    return out[:limit]
