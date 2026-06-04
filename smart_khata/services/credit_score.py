from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from commerce.models import Invoice, Payment
from khataapp.models import Party, Transaction as KhataTransaction
from smart_khata.models import PaymentBehavior

DECIMAL_AGG_FIELD = DecimalField(max_digits=14, decimal_places=2)


@dataclass(frozen=True)
class CreditScoreResult:
    score: int
    level: str
    timeliness_score: int
    frequency_score: int
    outstanding_score: int
    total_due: Decimal
    average_delay_days: int
    last_payment_date: Optional[date]


def credit_score_level(score: int) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Risky"
    return "High Risk"


def clamp_int(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(v)))


def get_invoice_due_date(invoice: Invoice) -> date:
    """
    Compute a due date for a customer invoice.

    Priority:
    - Order.payment_due_date (if present)
    - Invoice.created_at.date + Party.credit_period
    """
    try:
        order = invoice.order
    except Exception:
        order = None

    if order and getattr(order, "payment_due_date", None):
        return order.payment_due_date

    party = getattr(order, "party", None)
    credit_period = int(getattr(party, "credit_period", 30) or 30)
    base = (invoice.created_at.date() if getattr(invoice, "created_at", None) else timezone.localdate())
    return base + timedelta(days=credit_period)


def _paid_total_for_invoice(invoice: Invoice) -> Decimal:
    return (
        Payment.objects.filter(invoice=invoice, is_deleted=False).aggregate(
            total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_AGG_FIELD)
        )["total"]
        or Decimal("0.00")
    )


def invoice_is_fully_paid(invoice: Invoice) -> bool:
    try:
        if (invoice.status or "").lower() == "cancelled":
            return False
    except Exception:
        return False
    if not invoice.amount:
        return False
    return _paid_total_for_invoice(invoice) >= (invoice.amount or Decimal("0.00"))


def invoice_paid_date(invoice: Invoice) -> Optional[date]:
    """
    Determine the date when an invoice became fully paid (cumulative payments >= invoice.amount).
    """
    if not invoice.amount:
        return None

    payments = (
        Payment.objects.filter(invoice=invoice, is_deleted=False)
        .only("id", "amount", "created_at")
        .order_by("created_at", "id")
    )
    running = Decimal("0.00")
    target = invoice.amount or Decimal("0.00")
    for p in payments:
        try:
            running += (p.amount or Decimal("0.00"))
        except Exception:
            continue
        if running >= target:
            try:
                return p.created_at.date()
            except Exception:
                return timezone.localdate()
    return None


@transaction.atomic
def upsert_payment_behavior_for_invoice(invoice: Invoice) -> Optional[PaymentBehavior]:
    """
    Create/update PaymentBehavior when an invoice is fully paid.
    Returns the behavior row if created/updated, else None.
    """
    order = getattr(invoice, "order", None)
    party = getattr(order, "party", None)
    if not party or (party.party_type or "").lower() != "customer":
        return None

    if not invoice_is_fully_paid(invoice):
        return None

    paid_dt = invoice_paid_date(invoice)
    if not paid_dt:
        return None

    due_dt = get_invoice_due_date(invoice)
    delay = (paid_dt - due_dt).days
    if delay < 0:
        delay = 0

    owner = getattr(order, "owner", None) or getattr(party, "owner", None)
    if not owner:
        return None

    obj, _ = PaymentBehavior.objects.update_or_create(
        invoice=invoice,
        defaults={
            "owner": owner,
            "customer": party,
            "due_date": due_dt,
            "paid_date": paid_dt,
            "delay_days": int(delay),
        },
    )
    return obj


def _txn_balance_due_for_party(party: Party) -> Decimal:
    """
    Outstanding due from Khata transactions.

    Convention in this project:
    - balance = credits - debits (see Party.balance and party_list annotation)
    """
    credit_total = (
        KhataTransaction.objects.filter(party=party, is_deleted=False, txn_type="credit").aggregate(
            total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_AGG_FIELD)
        )["total"]
        or Decimal("0.00")
    )
    debit_total = (
        KhataTransaction.objects.filter(party=party, is_deleted=False, txn_type="debit").aggregate(
            total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_AGG_FIELD)
        )["total"]
        or Decimal("0.00")
    )
    bal = (credit_total or Decimal("0.00")) - (debit_total or Decimal("0.00"))
    return bal if bal > 0 else Decimal("0.00")


def _invoice_due_for_party(party: Party) -> Decimal:
    """
    Outstanding due from Commerce invoices for SALE orders.
    """
    invoice_total = (
        Invoice.objects.filter(order__party=party, order__owner=party.owner, order__order_type__iexact="sale")
        .exclude(status__iexact="cancelled")
        .aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_AGG_FIELD))["total"]
        or Decimal("0.00")
    )
    paid_total = (
        Payment.objects.filter(
            invoice__order__party=party,
            invoice__order__owner=party.owner,
            invoice__order__order_type__iexact="sale",
            is_deleted=False,
        ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_AGG_FIELD))["total"]
        or Decimal("0.00")
    )
    due = (invoice_total or Decimal("0.00")) - (paid_total or Decimal("0.00"))
    return due if due > 0 else Decimal("0.00")


def compute_credit_score(party: Party) -> CreditScoreResult:
    """
    Compute Smart Khata credit score for a customer.
    """
    if not party or (party.party_type or "").lower() != "customer":
        return CreditScoreResult(
            score=0,
            level="High Risk",
            timeliness_score=0,
            frequency_score=0,
            outstanding_score=0,
            total_due=Decimal("0.00"),
            average_delay_days=0,
            last_payment_date=None,
        )

    owner = party.owner
    today = timezone.localdate()

    # --- Timeliness (40%) ---
    recent_delays = list(
        PaymentBehavior.objects.filter(owner=owner, customer=party)
        .order_by("-created_at", "-id")
        .values_list("delay_days", flat=True)[:12]
    )
    if recent_delays:
        avg_delay = int(round(sum(int(x or 0) for x in recent_delays) / max(1, len(recent_delays))))
        # 0 days late => 100, 30+ days late => 0 (linear).
        timeliness_score = clamp_int(100 - int((avg_delay / 30) * 100))
    else:
        avg_delay = 0
        timeliness_score = 60  # Neutral when no history exists.

    # --- Frequency (30%) ---
    window_start = today - timedelta(days=90)
    payment_count = Payment.objects.filter(
        invoice__order__party=party,
        invoice__order__owner=owner,
        is_deleted=False,
        created_at__date__gte=window_start,
    ).count()
    txn_debit_count = KhataTransaction.objects.filter(
        party=party, is_deleted=False, txn_type="debit", date__gte=window_start
    ).count()
    freq_count = int(payment_count) + int(txn_debit_count)
    if freq_count <= 0 and not recent_delays:
        frequency_score = 50
    else:
        frequency_score = clamp_int(int((min(freq_count, 8) / 8) * 100))

    # --- Outstanding (30%) ---
    invoice_due = _invoice_due_for_party(party)
    txn_due = _txn_balance_due_for_party(party)
    total_due = (invoice_due or Decimal("0.00")) + (txn_due or Decimal("0.00"))

    year_start = today - timedelta(days=365)
    invoiced_365 = (
        Invoice.objects.filter(
            order__party=party,
            order__owner=owner,
            order__order_type__iexact="sale",
            created_at__date__gte=year_start,
        )
        .exclude(status__iexact="cancelled")
        .aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_AGG_FIELD))["total"]
        or Decimal("0.00")
    )
    baseline = max(invoiced_365, total_due, Decimal("1.00"))
    ratio = (total_due / baseline) if baseline else Decimal("1.00")
    if ratio < 0:
        ratio = Decimal("0.00")
    if ratio > 1:
        ratio = Decimal("1.00")
    outstanding_score = clamp_int(int((Decimal("1.00") - ratio) * 100))

    score = clamp_int(
        int(round((0.40 * timeliness_score) + (0.30 * frequency_score) + (0.30 * outstanding_score)))
    )
    level = credit_score_level(score)

    # last_payment_date: last Commerce payment OR last Khata debit txn
    last_payment = (
        Payment.objects.filter(invoice__order__party=party, invoice__order__owner=owner, is_deleted=False)
        .order_by("-created_at", "-id")
        .values_list("created_at", flat=True)
        .first()
    )
    last_payment_dt = last_payment.date() if last_payment else None
    last_txn = (
        KhataTransaction.objects.filter(party=party, is_deleted=False, txn_type="debit")
        .order_by("-date", "-id")
        .values_list("date", flat=True)
        .first()
    )
    if last_txn and (not last_payment_dt or last_txn > last_payment_dt):
        last_payment_dt = last_txn

    return CreditScoreResult(
        score=score,
        level=level,
        timeliness_score=timeliness_score,
        frequency_score=frequency_score,
        outstanding_score=outstanding_score,
        total_due=total_due,
        average_delay_days=avg_delay,
        last_payment_date=last_payment_dt,
    )


@transaction.atomic
def update_party_credit_metrics(party: Party) -> CreditScoreResult:
    """
    Recompute and persist Party.credit_score + related metrics.
    """
    result = compute_credit_score(party)
    if not party:
        return result

    update_fields = []
    if getattr(party, "credit_score", None) != result.score:
        party.credit_score = result.score
        update_fields.append("credit_score")
    if getattr(party, "average_payment_delay", None) != result.average_delay_days:
        party.average_payment_delay = result.average_delay_days
        update_fields.append("average_payment_delay")
    if getattr(party, "total_due", None) != result.total_due:
        party.total_due = result.total_due
        update_fields.append("total_due")
    if getattr(party, "last_payment_date", None) != result.last_payment_date:
        party.last_payment_date = result.last_payment_date
        update_fields.append("last_payment_date")

    if update_fields:
        Party.objects.filter(id=party.id).update(**{f: getattr(party, f) for f in update_fields})
    return result


@transaction.atomic
def sync_invoice_status(invoice: Invoice) -> None:
    """
    Keep Invoice.status in sync with payments.
    """
    if not invoice:
        return
    try:
        if (invoice.status or "").lower() == "cancelled":
            return
    except Exception:
        return

    paid_total = _paid_total_for_invoice(invoice)
    amount = invoice.amount or Decimal("0.00")
    should_be_paid = bool(amount and paid_total >= amount)
    new_status = "paid" if should_be_paid else "unpaid"
    if (invoice.status or "").lower() != new_status:
        Invoice.objects.filter(id=invoice.id).update(status=new_status)
