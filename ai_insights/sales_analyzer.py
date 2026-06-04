from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from commerce.models import Invoice, OrderItem
from accounts.models import Expense


@dataclass(frozen=True)
class TodaySales:
    total_amount: Decimal
    invoice_count: int


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def compute_today_sales(owner) -> TodaySales:
    today = timezone.localdate()
    qs = Invoice.objects.filter(order__owner=owner, created_at__date=today)
    total = _to_decimal(qs.aggregate(s=Sum("amount")).get("s") or 0)
    return TodaySales(total_amount=total, invoice_count=qs.count())


def compute_sales_trend(owner, *, days: int = 14) -> list[dict]:
    """
    Returns [{date, total}] for last N days.
    """
    days = max(7, min(int(days or 14), 90))
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)
    rows = (
        Invoice.objects.filter(order__owner=owner, created_at__date__gte=start, created_at__date__lte=end)
        .values("created_at__date")
        .annotate(total=Sum("amount"))
        .order_by("created_at__date")
    )
    out = []
    for r in rows:
        out.append({"date": str(r["created_at__date"]), "total": float(_to_decimal(r["total"] or 0))})
    return out


def compute_top_selling_products(owner, *, limit: int = 5) -> list[dict]:
    limit = max(3, min(int(limit or 5), 20))
    rows = (
        OrderItem.objects.filter(order__owner=owner, order__order_type="SALE")
        .values("product__name")
        .annotate(qty=Sum("qty"))
        .order_by("-qty")[:limit]
    )
    return [{"name": r["product__name"] or "Unknown", "qty": float(r["qty"] or 0)} for r in rows]


def compute_profit_summary(owner, *, days: int = 30) -> dict:
    """
    Simple profit summary:
    sales - purchases - expenses (cashflow-ish, not COGS-accurate).
    """
    days = max(7, min(int(days or 30), 365))
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)

    sales_qs = Invoice.objects.filter(order__owner=owner, order__order_type="SALE", created_at__date__gte=start, created_at__date__lte=end)
    purchase_qs = Invoice.objects.filter(order__owner=owner, order__order_type="PURCHASE", created_at__date__gte=start, created_at__date__lte=end)
    expense_qs = Expense.objects.filter(created_by=owner, expense_date__gte=start, expense_date__lte=end)

    sales_total = _to_decimal(sales_qs.aggregate(s=Sum("amount")).get("s") or 0)
    purchase_total = _to_decimal(purchase_qs.aggregate(s=Sum("amount")).get("s") or 0)
    expense_total = _to_decimal(expense_qs.aggregate(s=Sum("amount_paid")).get("s") or 0)

    profit = sales_total - purchase_total - expense_total
    return {
        "days": days,
        "start": str(start),
        "end": str(end),
        "sales": float(sales_total),
        "purchases": float(purchase_total),
        "expenses": float(expense_total),
        "profit": float(profit),
    }
