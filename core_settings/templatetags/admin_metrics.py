from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone


register = template.Library()


def _to_int(v) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def _to_decimal(v) -> Decimal:
    try:
        return Decimal(str(v or "0"))
    except Exception:
        return Decimal("0")


@register.simple_tag
def admin_dashboard_metrics(days: int = 14) -> Dict[str, Any]:
    """
    Build Notus-like dashboard metrics for the admin index.

    Safe-by-default:
    - all queries are wrapped so missing apps/migrations won't break admin.
    """
    User = get_user_model()
    now = timezone.now()
    start = now - timedelta(days=int(days) - 1)

    metrics: Dict[str, Any] = {
        "users_total": 0,
        "users_active": 0,
        "vendors_total": 0,
        "store_orders_total": 0,
        "store_revenue_total": "0",
        "orders_series_labels": [],
        "orders_series_values": [],
        "orders_series_labels_json": "[]",
        "orders_series_values_json": "[]",
        "payment_breakdown": {"unpaid": 0, "initiated": 0, "paid": 0, "failed": 0},
        "payment_breakdown_json": "{}",
        "latest_users": [],
        "latest_orders": [],
    }

    # Users
    try:
        metrics["users_total"] = User.objects.count()
        metrics["users_active"] = User.objects.filter(is_active=True).count()
        metrics["latest_users"] = list(
            User.objects.order_by("-id").values("id", "email", "mobile", "is_active")[:7]
        )
    except Exception:
        pass

    # Vendors
    try:
        from vendors.models import Vendor

        metrics["vendors_total"] = Vendor.objects.count()
    except Exception:
        pass

    # Storefront orders + revenue + series
    try:
        from storefront.models import StoreOrder

        metrics["store_orders_total"] = StoreOrder.objects.count()
        revenue = StoreOrder.objects.filter(status__in=["accepted", "packed", "shipped", "delivered"]).aggregate(
            s=Sum("total_amount")
        )["s"]
        metrics["store_revenue_total"] = str(_to_decimal(revenue))

        # last N days series
        qs = (
            StoreOrder.objects.filter(created_at__date__gte=start.date())
            .extra(select={"d": "date(created_at)"})
            .values("d")
            .annotate(c=Count("id"))
            .order_by("d")
        )
        counts_by_day = {str(row["d"]): _to_int(row["c"]) for row in qs}
        labels: List[str] = []
        values: List[int] = []
        for i in range(int(days)):
            d = (start + timedelta(days=i)).date()
            key = str(d)
            labels.append(d.strftime("%d %b"))
            values.append(counts_by_day.get(key, 0))
        metrics["orders_series_labels"] = labels
        metrics["orders_series_values"] = values
        metrics["orders_series_labels_json"] = json.dumps(labels)
        metrics["orders_series_values_json"] = json.dumps(values)

        # payment breakdown
        pb = dict(
            StoreOrder.objects.values("payment_status").annotate(c=Count("id")).values_list("payment_status", "c")
        )
        metrics["payment_breakdown"] = {
            "unpaid": _to_int(pb.get("unpaid")),
            "initiated": _to_int(pb.get("initiated")),
            "paid": _to_int(pb.get("paid")),
            "failed": _to_int(pb.get("failed")),
        }
        metrics["payment_breakdown_json"] = json.dumps(metrics["payment_breakdown"])

        metrics["latest_orders"] = list(
            StoreOrder.objects.select_related("vendor", "customer")
            .order_by("-created_at")
            .values("id", "order_number", "status", "payment_status", "total_amount", "created_at")[:7]
        )
    except Exception:
        pass

    return metrics
