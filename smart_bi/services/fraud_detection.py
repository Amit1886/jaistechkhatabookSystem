from __future__ import annotations

import logging
from decimal import Decimal
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from commerce.models import Invoice, Payment
from smart_bi.models import FraudAlert

logger = logging.getLogger(__name__)


def _to_decimal(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0.00")


def detect_invoice_anomaly(*, invoice: Invoice) -> None:
    """
    Simple anomaly detection:
    - if invoice amount is much higher than recent average, raise alert.
    """
    try:
        order = getattr(invoice, "order", None)
        owner = getattr(order, "owner", None)
        if not owner:
            return
        amt = _to_decimal(getattr(invoice, "amount", 0))
        if amt <= 0:
            return
        since = timezone.now() - timedelta(days=30)
        base = (
            Invoice.objects.filter(order__owner=owner, created_at__gte=since)
            .aggregate(avg=Avg("amount"), cnt=Count("id"))
        )
        avg = _to_decimal(base.get("avg") or 0)
        cnt = int(base.get("cnt") or 0)
        if cnt < 8 or avg <= 0:
            return

        # Spike threshold: > 3.5x average or > avg + 5*avg (same thing); cap by minimum absolute delta
        if amt >= (avg * Decimal("3.5")) and (amt - avg) >= Decimal("5000"):
            FraudAlert.objects.create(
                owner=owner,
                kind=FraudAlert.Kind.INVOICE_SPIKE,
                score=85,
                message=f"Invoice amount spike detected: ₹{amt} (avg ₹{avg})",
                payload={"invoice_id": invoice.id, "invoice_number": invoice.number, "amount": str(amt), "avg_30d": str(avg)},
                reference_type="commerce.Invoice",
                reference_id=str(invoice.id),
            )
    except Exception:
        logger.exception("Invoice anomaly detection failed")


def detect_payment_anomaly(*, payment: Payment) -> None:
    """
    Simple anomaly detection:
    - if payment amount is unusually high vs recent average, raise alert.
    """
    try:
        inv = getattr(payment, "invoice", None)
        order = getattr(inv, "order", None) if inv else None
        owner = getattr(order, "owner", None)
        if not owner:
            return
        amt = _to_decimal(getattr(payment, "amount", 0))
        if amt <= 0:
            return
        since = timezone.now() - timedelta(days=30)
        base = (
            Payment.objects.filter(invoice__order__owner=owner, created_at__gte=since, is_deleted=False)
            .aggregate(avg=Avg("amount"), cnt=Count("id"))
        )
        avg = _to_decimal(base.get("avg") or 0)
        cnt = int(base.get("cnt") or 0)
        if cnt < 8 or avg <= 0:
            return

        if amt >= (avg * Decimal("4.0")) and (amt - avg) >= Decimal("5000"):
            FraudAlert.objects.create(
                owner=owner,
                kind=FraudAlert.Kind.PAYMENT_SPIKE,
                score=80,
                message=f"Payment amount spike detected: ₹{amt} (avg ₹{avg})",
                payload={"payment_id": payment.id, "amount": str(amt), "avg_30d": str(avg), "invoice_id": getattr(inv, "id", None)},
                reference_type="commerce.Payment",
                reference_id=str(payment.id),
            )
    except Exception:
        logger.exception("Payment anomaly detection failed")

