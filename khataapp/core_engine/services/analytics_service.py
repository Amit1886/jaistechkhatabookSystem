from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from khataapp.core_engine.services.plan_access import get_locked_engine_features, get_user_plan_label
from khataapp.core_engine.utils.engine import get_engine


@dataclass(frozen=True)
class AnalyticsSnapshot:
    payload: dict
    tips: list[str]


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def compute_snapshot(owner) -> AnalyticsSnapshot:
    today = timezone.localdate()
    start_7 = today - timedelta(days=6)

    # Lazy imports to avoid any startup cycles.
    from commerce.models import Invoice, Payment
    from khataapp.models import Party, Transaction

    parties = Party.objects.filter(owner=owner).count()
    txns = Transaction.objects.filter(party__owner=owner, is_deleted=False).count()
    sales_invoices = Invoice.objects.filter(order__owner=owner, order__order_type="SALE").count()
    payments = Payment.objects.filter(invoice__order__owner=owner, is_deleted=False).count()

    weekly_sales = (
        Invoice.objects.filter(order__owner=owner, order__order_type="SALE", created_at__date__gte=start_7)
        .aggregate(t=Sum("amount"))
        .get("t")
        or Decimal("0.00")
    )
    weekly_payments = (
        Payment.objects.filter(invoice__order__owner=owner, created_at__date__gte=start_7, is_deleted=False)
        .aggregate(t=Sum("amount"))
        .get("t")
        or Decimal("0.00")
    )

    engine = get_engine(owner)
    locked = get_locked_engine_features(owner)

    payload = {
        "date": str(today),
        "plan": get_user_plan_label(owner),
        "parties": parties,
        "transactions": txns,
        "sales_invoices": sales_invoices,
        "payments": payments,
        "weekly_sales": str(_d(weekly_sales).quantize(Decimal("0.01"))),
        "weekly_payments": str(_d(weekly_payments).quantize(Decimal("0.01"))),
        "engine": {
            "total_rewards": int(getattr(engine, "total_rewards", 0) or 0),
            "reward_points": int(getattr(engine, "reward_points", 0) or 0),
            "referral_earnings": str(getattr(engine, "referral_earnings", Decimal("0.00"))),
            "payment_commission_earned": str(getattr(engine, "payment_commission_earned", Decimal("0.00"))),
            "whatsapp_credits": int(getattr(engine, "whatsapp_credits", 0) or 0),
            "loyalty_points": int(getattr(engine, "loyalty_points", 0) or 0),
            "daily_task_streak": int(getattr(engine, "daily_task_streak", 0) or 0),
            "level": int(getattr(engine, "level", 1) or 1),
            "locked_features": locked,
            "referral_code": getattr(engine, "referral_code", "") if engine else "",
        },
    }

    tips: list[str] = []
    if parties < 5:
        tips.append("Add more parties to unlock smarter follow-ups and loyalty rewards.")
    if _d(weekly_sales) > 0 and (_d(weekly_payments) / max(_d(weekly_sales), Decimal("1"))) < Decimal("0.6"):
        tips.append("Outstanding dues look high. Send a WhatsApp payment reminder to improve collections.")
    if locked:
        tips.append("Upgrade your plan to unlock premium growth features.")
    if not tips:
        tips.append("You are on track. Keep recording daily transactions to grow your streak.")

    return AnalyticsSnapshot(payload=payload, tips=tips)


def update_engine_snapshot(owner) -> AnalyticsSnapshot:
    snap = compute_snapshot(owner)
    engine = get_engine(owner)
    if engine:
        engine.analytics_snapshot = snap.payload
        engine.plan_locked_features = snap.payload.get("engine", {}).get("locked_features", [])
        engine.save(update_fields=["analytics_snapshot", "plan_locked_features", "updated_at"])
    return snap

