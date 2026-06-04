from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type, timedelta
from decimal import Decimal

from django.db.models import DecimalField, F, Sum
from django.utils import timezone

from accounts.models import Expense
from commerce.models import Inventory, Invoice, Payment
from smart_bi.models import BusinessMetric


@dataclass(frozen=True)
class HealthLevel:
    label: str
    css_class: str


def health_level(score: int) -> HealthLevel:
    try:
        score_i = int(score)
    except Exception:
        score_i = 0
    if score_i >= 80:
        return HealthLevel(label="Excellent", css_class="success")
    if score_i >= 60:
        return HealthLevel(label="Good", css_class="primary")
    if score_i >= 40:
        return HealthLevel(label="Average", css_class="warning")
    return HealthLevel(label="Critical", css_class="danger")


def _clamp_score(x: Decimal) -> int:
    if x < 0:
        return 0
    if x > 100:
        return 100
    return int(x)


def _sum_decimal(qs, field: str) -> Decimal:
    return qs.aggregate(t=Sum(field))["t"] or Decimal("0.00")


def _sum_invoice_amount(owner, *, order_type: str, day: date_type) -> Decimal:
    return (
        Invoice.objects.filter(order__owner=owner, order__order_type=order_type, created_at__date=day)
        .aggregate(t=Sum("amount"))["t"]
        or Decimal("0.00")
    )


def _stock_value(owner) -> Decimal:
    money_field = DecimalField(max_digits=14, decimal_places=2)
    return (
        Inventory.objects.filter(owner=owner)
        .aggregate(t=Sum(F("stock") * F("product__price"), output_field=money_field))["t"]
        or Decimal("0.00")
    )


def _outstanding_due(owner, *, as_of: date_type) -> Decimal:
    """
    Outstanding dues (receivables) as-of the given date.

    Uses payments up to that date. Avoids nested DB aggregates by computing in two queries.
    """
    inv_rows = list(
        Invoice.objects.filter(
            order__owner=owner,
            order__order_type="SALE",
            created_at__date__lte=as_of,
        )
        .exclude(status="cancelled")
        .values("id", "amount")
    )
    if not inv_rows:
        return Decimal("0.00")

    inv_ids = [r["id"] for r in inv_rows]
    paid_by_invoice = {
        r["invoice_id"]: (r["t"] or Decimal("0.00"))
        for r in Payment.objects.filter(
            invoice_id__in=inv_ids,
            is_deleted=False,
            created_at__date__lte=as_of,
        )
        .values("invoice_id")
        .annotate(t=Sum("amount"))
    }

    total = Decimal("0.00")
    for r in inv_rows:
        amt = Decimal(str(r.get("amount") or 0))
        paid = Decimal(str(paid_by_invoice.get(r["id"]) or 0))
        due = amt - paid
        if due > 0:
            total += due
    return total.quantize(Decimal("0.01"))


def _sales_sum(owner, *, start_day: date_type, end_day: date_type) -> Decimal:
    return (
        Invoice.objects.filter(order__owner=owner, order__order_type="SALE", created_at__date__gte=start_day, created_at__date__lte=end_day)
        .aggregate(t=Sum("amount"))["t"]
        or Decimal("0.00")
    )


def _component_scores(
    *,
    sales_growth_pct: Decimal,
    profit_margin_pct: Decimal,
    expense_ratio_pct: Decimal,
    stock_turnover_30d: Decimal,
    outstanding_ratio_30d: Decimal,
) -> dict[str, int]:
    # Sales growth: -20% => 0, 0% => 50, +20% => 100
    growth_score = _clamp_score(((sales_growth_pct + Decimal("20.0")) / Decimal("40.0")) * Decimal("100.0"))

    # Profit margin: 0% => 0, 20%+ => 100
    if profit_margin_pct <= 0:
        margin_score = 0
    else:
        margin_score = _clamp_score((profit_margin_pct / Decimal("20.0")) * Decimal("100.0"))

    # Expense ratio: 10% => 100, 60% => 0
    if expense_ratio_pct <= Decimal("10.0"):
        expense_score = 100
    elif expense_ratio_pct >= Decimal("60.0"):
        expense_score = 0
    else:
        expense_score = _clamp_score(Decimal("100.0") - ((expense_ratio_pct - Decimal("10.0")) / Decimal("50.0")) * Decimal("100.0"))

    # Stock turnover: 0.5 => 0, 3.0+ => 100
    if stock_turnover_30d <= Decimal("0.5"):
        turnover_score = 0
    elif stock_turnover_30d >= Decimal("3.0"):
        turnover_score = 100
    else:
        turnover_score = _clamp_score(((stock_turnover_30d - Decimal("0.5")) / Decimal("2.5")) * Decimal("100.0"))

    # Outstanding dues ratio: 10% => 100, 80% => 0
    if outstanding_ratio_30d <= Decimal("0.10"):
        due_score = 100
    elif outstanding_ratio_30d >= Decimal("0.80"):
        due_score = 0
    else:
        due_score = _clamp_score(Decimal("100.0") - ((outstanding_ratio_30d - Decimal("0.10")) / Decimal("0.70")) * Decimal("100.0"))

    return {
        "sales_growth": growth_score,
        "profit_margin": margin_score,
        "expense_ratio": expense_score,
        "stock_turnover": turnover_score,
        "outstanding_dues": due_score,
    }


def compute_business_metric(owner, *, day: date_type | None = None) -> BusinessMetric:
    day = day or timezone.localdate()

    total_sales = _sum_invoice_amount(owner, order_type="SALE", day=day)
    total_purchase = _sum_invoice_amount(owner, order_type="PURCHASE", day=day)
    total_expense = _sum_decimal(Expense.objects.filter(created_by=owner, expense_date=day), "amount_paid")

    total_profit = (total_sales - total_purchase - total_expense).quantize(Decimal("0.01"))
    outstanding_due = _outstanding_due(owner, as_of=day)
    stock_value = _stock_value(owner).quantize(Decimal("0.01"))

    # Components (use trailing windows ending at `day`)
    sales_7d = _sales_sum(owner, start_day=day - timedelta(days=6), end_day=day)
    sales_prev_7d = _sales_sum(owner, start_day=day - timedelta(days=13), end_day=day - timedelta(days=7))
    if sales_prev_7d > 0:
        sales_growth_pct = ((sales_7d - sales_prev_7d) / sales_prev_7d) * Decimal("100.0")
    else:
        sales_growth_pct = Decimal("100.0") if sales_7d > 0 else Decimal("0.0")

    profit_margin_pct = (total_profit / total_sales) * Decimal("100.0") if total_sales > 0 else Decimal("0.0")
    expense_ratio_pct = (total_expense / total_sales) * Decimal("100.0") if total_sales > 0 else Decimal("0.0")

    sales_30d = _sales_sum(owner, start_day=day - timedelta(days=29), end_day=day)
    stock_turnover_30d = (sales_30d / stock_value) if stock_value > 0 else Decimal("0.0")
    outstanding_ratio_30d = (outstanding_due / sales_30d) if sales_30d > 0 else Decimal("0.0")

    components = _component_scores(
        sales_growth_pct=sales_growth_pct,
        profit_margin_pct=profit_margin_pct,
        expense_ratio_pct=expense_ratio_pct,
        stock_turnover_30d=stock_turnover_30d,
        outstanding_ratio_30d=outstanding_ratio_30d,
    )

    health_score = int(round(sum(components.values()) / 5.0)) if components else 0
    if health_score < 0:
        health_score = 0
    if health_score > 100:
        health_score = 100

    return BusinessMetric(
        owner=owner,
        date=day,
        total_sales=total_sales.quantize(Decimal("0.01")),
        total_profit=total_profit,
        total_expense=total_expense.quantize(Decimal("0.01")),
        outstanding_due=outstanding_due,
        stock_value=stock_value,
        health_score=health_score,
        computed_at=timezone.now(),
    )


def upsert_business_metric(owner, *, day: date_type | None = None) -> BusinessMetric:
    day = day or timezone.localdate()
    metric = compute_business_metric(owner, day=day)
    obj, _ = BusinessMetric.objects.update_or_create(
        owner=owner,
        date=day,
        defaults={
            "total_sales": metric.total_sales,
            "total_profit": metric.total_profit,
            "total_expense": metric.total_expense,
            "outstanding_due": metric.outstanding_due,
            "stock_value": metric.stock_value,
            "health_score": metric.health_score,
            "computed_at": metric.computed_at,
        },
    )
    return obj


def get_chart_series(owner, *, day: date_type | None = None) -> dict[str, list]:
    """
    Build chart series for UI/API. Ensures the last 7 days exist in business_metrics.
    """
    day = day or timezone.localdate()
    days = [day - timedelta(days=i) for i in range(6, -1, -1)]
    metrics_by_day = {m.date: m for m in BusinessMetric.objects.filter(owner=owner, date__gte=days[0], date__lte=days[-1])}
    for d in days:
        if d not in metrics_by_day:
            metrics_by_day[d] = upsert_business_metric(owner, day=d)

    labels = [d.strftime("%d %b") for d in days]
    daily_sales = [str(metrics_by_day[d].total_sales) for d in days]
    daily_profit = [str(metrics_by_day[d].total_profit) for d in days]
    daily_expense = [str(metrics_by_day[d].total_expense) for d in days]
    daily_due = [str(metrics_by_day[d].outstanding_due) for d in days]
    daily_turnover = []
    for d in days:
        m = metrics_by_day[d]
        try:
            sv = Decimal(str(m.stock_value or 0))
            ratio = (Decimal(str(m.total_sales or 0)) / sv) if sv > 0 else Decimal("0.0")
        except Exception:
            ratio = Decimal("0.0")
        daily_turnover.append(str(ratio.quantize(Decimal("0.01"))))

    return {
        "labels": labels,
        "daily_sales": daily_sales,
        "daily_profit": daily_profit,
        "daily_expense": daily_expense,
        "daily_due": daily_due,
        "daily_turnover": daily_turnover,
    }
