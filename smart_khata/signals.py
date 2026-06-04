from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.utils import OperationalError, ProgrammingError

from commerce.models import Invoice, Payment
from khataapp.models import Transaction as KhataTransaction
from smart_khata.services.credit_score import (
    invoice_is_fully_paid,
    sync_invoice_status,
    update_party_credit_metrics,
    upsert_payment_behavior_for_invoice,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payment)
def smart_khata_on_payment_saved(sender, instance: Payment, created: bool, **kwargs):
    try:
        invoice = instance.invoice
    except Exception:
        return
    if not invoice:
        return

    try:
        sync_invoice_status(invoice)
        if invoice_is_fully_paid(invoice):
            upsert_payment_behavior_for_invoice(invoice)
        else:
            # If a payment is deleted/edited and invoice becomes unpaid again,
            # remove stale behavior so score reflects current state.
            from smart_khata.models import PaymentBehavior

            PaymentBehavior.objects.filter(invoice=invoice).delete()

        order = getattr(invoice, "order", None)
        party = getattr(order, "party", None)
        if party and (party.party_type or "").lower() == "customer":
            update_party_credit_metrics(party)
    except (OperationalError, ProgrammingError):
        # Migrations not ready yet (fresh DB) or DB locked.
        return
    except Exception:
        logger.exception("Smart Khata: payment signal failed (payment_id=%s)", getattr(instance, "id", None))


@receiver(post_save, sender=Invoice)
def smart_khata_on_invoice_saved(sender, instance: Invoice, created: bool, **kwargs):
    try:
        order = instance.order
        party = getattr(order, "party", None)
    except Exception:
        return

    if not party or (party.party_type or "").lower() != "customer":
        return

    try:
        # New invoice increases due amount; recompute score metrics.
        update_party_credit_metrics(party)
    except (OperationalError, ProgrammingError):
        return
    except Exception:
        logger.exception("Smart Khata: invoice signal failed (invoice_id=%s)", getattr(instance, "id", None))


@receiver(post_save, sender=KhataTransaction)
def smart_khata_on_khata_txn_saved(sender, instance: KhataTransaction, created: bool, **kwargs):
    party = getattr(instance, "party", None)
    if not party or (party.party_type or "").lower() != "customer":
        return
    try:
        update_party_credit_metrics(party)
    except (OperationalError, ProgrammingError):
        return
    except Exception:
        logger.exception("Smart Khata: transaction signal failed (txn_id=%s)", getattr(instance, "id", None))
