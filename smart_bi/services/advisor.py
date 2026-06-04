from __future__ import annotations

from decimal import Decimal
from typing import Any

from ai_insights.stock_analyzer import compute_low_stock, compute_reorder_suggestions
from smart_bi.models import FraudAlert
from whatsapp.models import WhatsAppAccount


def advisor_suggestions(owner, *, metric=None) -> list[dict[str, Any]]:
    """
    Next-gen, explainable business advisor suggestions.

    This is "self-learning" in the sense that it reacts to the shop's data patterns.
    Heavy ML can be added later, but this works offline and is stable.
    """
    tips: list[dict[str, Any]] = []

    # WhatsApp connectivity
    if not WhatsAppAccount.objects.filter(owner=owner, is_active=True, status=WhatsAppAccount.Status.CONNECTED).exists():
        tips.append(
            {
                "title": "Connect WhatsApp",
                "detail": "Connect your WhatsApp number to automate invoices, reminders, orders and support.",
                "action": "/whatsapp/setup/",
            }
        )

    # Fraud alerts
    if FraudAlert.objects.filter(owner=owner, is_resolved=False).exists():
        tips.append(
            {
                "title": "Review Fraud Alerts",
                "detail": "Some invoices/payments look unusual compared to your recent pattern.",
                "action": "/superadmin/smart_bi/fraudalert/",
            }
        )

    # Stock / reorder
    low_stock = compute_low_stock(owner, limit=5)
    if low_stock:
        tips.append(
            {
                "title": "Low Stock Items",
                "detail": f"{len(low_stock)} products are low stock. Consider reordering today.",
                "action": "/ai-insights/",
            }
        )

    reorder = compute_reorder_suggestions(owner, days=30, limit=5)
    if reorder:
        tips.append(
            {
                "title": "Purchase Prediction",
                "detail": "Based on last 30 days sales, some products may run out soon.",
                "action": "/ai-insights/",
            }
        )

    # Dues / collections (from BusinessMetric if provided)
    try:
        outstanding = Decimal(str(getattr(metric, "outstanding_due", 0) or 0))
    except Exception:
        outstanding = Decimal("0.00")
    if outstanding >= Decimal("5000"):
        tips.append(
            {
                "title": "Send Payment Reminders",
                "detail": f"Outstanding dues are ₹{outstanding}. Send WhatsApp reminders to improve cashflow.",
                "action": "/whatsapp/control-center/",
            }
        )

    return tips[:6]

