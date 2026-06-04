from __future__ import annotations

import logging

from django.apps import apps
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ledger.models import LedgerTransaction, StockLedger, StockTransfer, JournalVoucher, ReturnNote
from ledger.services.posting import (
    post_expense,
    post_invoice,
    post_journal_voucher,
    post_return_note,
    post_khata_transaction,
    post_payment,
    post_stock_transfer,
    post_supplier_payment,
    schedule_on_commit,
)

logger = logging.getLogger(__name__)


# Lazy model resolution (ledger app is imported in AppConfig.ready())
Invoice = apps.get_model("commerce", "Invoice")
Payment = apps.get_model("commerce", "Payment")
KhataTransaction = apps.get_model("khataapp", "Transaction")
SupplierPayment = apps.get_model("khataapp", "SupplierPayment")
Expense = apps.get_model("accounts", "Expense")


# -----------------------------
# Commerce: Invoice / Payment
# -----------------------------

@receiver(post_save, sender=Invoice)
def gl_post_invoice(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_invoice, instance.id)
    except Exception:
        logger.exception("GL posting failed for commerce.Invoice id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=Invoice)
def gl_void_invoice(sender, instance, **kwargs):
    try:
        # Remove both GL + stock for the deleted invoice
        LedgerTransaction.objects.filter(
            reference_type="commerce.Invoice",
            reference_id=getattr(instance, "id", None),
            voucher_type__in=[
                LedgerTransaction.VoucherType.SALES_INVOICE,
                LedgerTransaction.VoucherType.PURCHASE_INVOICE,
            ],
        ).delete()
        StockLedger.objects.filter(
            reference_type="commerce.Invoice",
            reference_id=getattr(instance, "id", None),
        ).delete()
    except Exception:
        logger.exception("GL void failed for commerce.Invoice id=%s", getattr(instance, "id", None))


@receiver(post_save, sender=Payment)
def gl_post_payment(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_payment, instance.id)
    except Exception:
        logger.exception("GL posting failed for commerce.Payment id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=Payment)
def gl_void_payment(sender, instance, **kwargs):
    try:
        LedgerTransaction.objects.filter(
            reference_type="commerce.Payment",
            reference_id=getattr(instance, "id", None),
            voucher_type__in=[
                LedgerTransaction.VoucherType.RECEIPT,
                LedgerTransaction.VoucherType.PAYMENT,
            ],
        ).delete()
    except Exception:
        logger.exception("GL void failed for commerce.Payment id=%s", getattr(instance, "id", None))


# -----------------------------
# Khata: manual Transaction / SupplierPayment
# -----------------------------

@receiver(post_save, sender=KhataTransaction)
def gl_post_khata_txn(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_khata_transaction, instance.id)
    except Exception:
        logger.exception("GL posting failed for khataapp.Transaction id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=KhataTransaction)
def gl_void_khata_txn(sender, instance, **kwargs):
    try:
        LedgerTransaction.objects.filter(
            reference_type="khataapp.Transaction",
            reference_id=getattr(instance, "id", None),
            voucher_type__in=[
                LedgerTransaction.VoucherType.RECEIPT,
                LedgerTransaction.VoucherType.PAYMENT,
            ],
        ).delete()
    except Exception:
        logger.exception("GL void failed for khataapp.Transaction id=%s", getattr(instance, "id", None))


@receiver(post_save, sender=SupplierPayment)
def gl_post_supplier_payment(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_supplier_payment, instance.id)
    except Exception:
        logger.exception("GL posting failed for khataapp.SupplierPayment id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=SupplierPayment)
def gl_void_supplier_payment(sender, instance, **kwargs):
    try:
        LedgerTransaction.objects.filter(
            reference_type="khataapp.SupplierPayment",
            reference_id=getattr(instance, "id", None),
            voucher_type=LedgerTransaction.VoucherType.PAYMENT,
        ).delete()
    except Exception:
        logger.exception("GL void failed for khataapp.SupplierPayment id=%s", getattr(instance, "id", None))


# -----------------------------
# Accounts: Expense
# -----------------------------

@receiver(post_save, sender=Expense)
def gl_post_expense(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_expense, instance.id)
    except Exception:
        logger.exception("GL posting failed for accounts.Expense id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=Expense)
def gl_void_expense(sender, instance, **kwargs):
    try:
        LedgerTransaction.objects.filter(
            reference_type="accounts.Expense",
            reference_id=getattr(instance, "id", None),
            voucher_type=LedgerTransaction.VoucherType.EXPENSE,
        ).delete()
    except Exception:
        logger.exception("GL void failed for accounts.Expense id=%s", getattr(instance, "id", None))


# -----------------------------
# Ledger app: StockTransfer / JournalVoucher
# -----------------------------

@receiver(post_save, sender=StockTransfer)
def stock_post_transfer(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_stock_transfer, instance.id)
    except Exception:
        logger.exception("Stock posting failed for ledger.StockTransfer id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=StockTransfer)
def stock_void_transfer(sender, instance, **kwargs):
    try:
        StockLedger.objects.filter(
            reference_type="ledger.StockTransfer",
            reference_id=getattr(instance, "id", None),
        ).delete()
    except Exception:
        logger.exception("Stock void failed for ledger.StockTransfer id=%s", getattr(instance, "id", None))


@receiver(post_save, sender=JournalVoucher)
def gl_post_journal_voucher(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_journal_voucher, instance.id)
    except Exception:
        logger.exception("GL posting failed for ledger.JournalVoucher id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=JournalVoucher)
def gl_void_journal_voucher(sender, instance, **kwargs):
    try:
        LedgerTransaction.objects.filter(
            reference_type="ledger.JournalVoucher",
            reference_id=getattr(instance, "id", None),
            voucher_type=LedgerTransaction.VoucherType.JOURNAL,
        ).delete()
    except Exception:
        logger.exception("GL void failed for ledger.JournalVoucher id=%s", getattr(instance, "id", None))


@receiver(post_save, sender=ReturnNote)
def gl_post_return_note(sender, instance, **kwargs):
    try:
        schedule_on_commit(post_return_note, instance.id)
    except Exception:
        logger.exception("GL posting failed for ledger.ReturnNote id=%s", getattr(instance, "id", None))


@receiver(post_delete, sender=ReturnNote)
def gl_void_return_note(sender, instance, **kwargs):
    try:
        LedgerTransaction.objects.filter(
            reference_type="ledger.ReturnNote",
            reference_id=getattr(instance, "id", None),
            voucher_type__in=[
                LedgerTransaction.VoucherType.CREDIT_NOTE,
                LedgerTransaction.VoucherType.DEBIT_NOTE,
            ],
        ).delete()
        StockLedger.objects.filter(
            reference_type="ledger.ReturnNote",
            reference_id=getattr(instance, "id", None),
        ).delete()
    except Exception:
        logger.exception("GL void failed for ledger.ReturnNote id=%s", getattr(instance, "id", None))
