from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from khataapp.models import Transaction


def _money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def create_party_transaction_once(
    *,
    party,
    txn_type: str,
    amount,
    date=None,
    txn_mode: str = "cash",
    notes: str = "",
    order=None,
    invoice=None,
    payment=None,
    voucher=None,
    voucher_type: str = "",
    created_by=None,
    gst_type: str | None = None,
):
    """
    Idempotent party-ledger transaction writer.

    Older flows created khata credit rows alongside commerce.Payment rows. This
    helper allows those flows to stay compatible while preventing duplicate
    credit/payment mirrors for the same invoice/payment/reference.
    """
    amount = _money(amount)
    txn_date = date or timezone.localdate()
    clean_type = (txn_type or "").strip().lower()
    if clean_type not in {"credit", "debit"}:
        raise ValueError("txn_type must be credit or debit")
    if amount <= 0:
        raise ValueError("amount must be greater than zero")

    with transaction.atomic():
        qs = Transaction.objects.select_for_update().filter(
            party=party,
            txn_type=clean_type,
            amount=amount,
            date=txn_date,
            is_deleted=False,
        )
        if payment is not None:
            existing = qs.filter(payment=payment).first()
            if existing:
                return existing, False
        if invoice is not None:
            existing = qs.filter(invoice=invoice).first()
            if existing:
                return existing, False
        if order is not None and voucher_type:
            existing = qs.filter(order=order, voucher_type=voucher_type).first()
            if existing:
                return existing, False
        if notes:
            existing = qs.filter(notes=notes).first()
            if existing:
                return existing, False

        obj = Transaction.objects.create(
            party=party,
            txn_type=clean_type,
            txn_mode=txn_mode or "cash",
            amount=amount,
            date=txn_date,
            notes=notes or "",
            order=order,
            invoice=invoice,
            payment=payment,
            voucher=voucher,
            voucher_type=voucher_type or None,
            created_by=created_by,
            gst_type=gst_type,
        )
        return obj, True
