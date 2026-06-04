from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from ledger.models import (
    JournalVoucher,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    StockLedger,
    StockTransfer,
)

logger = logging.getLogger(__name__)


# -----------------------------
# Ledger Account Helpers
# -----------------------------

SYSTEM_ACCOUNTS = {
    "CASH": ("Cash", LedgerAccount.AccountType.ASSET),
    "BANK": ("Bank", LedgerAccount.AccountType.ASSET),
    "SALES": ("Sales", LedgerAccount.AccountType.INCOME),
    "PURCHASE": ("Purchase", LedgerAccount.AccountType.EXPENSE),
    "OUTPUT_GST": ("Output GST", LedgerAccount.AccountType.LIABILITY),
    "INPUT_GST": ("Input GST", LedgerAccount.AccountType.ASSET),
}


def _to_decimal(value, default=Decimal("0.00")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return default


def get_or_create_system_account(owner, code: str) -> LedgerAccount:
    code = (code or "").strip().upper()
    if code not in SYSTEM_ACCOUNTS:
        raise ValueError(f"Unknown system account code: {code}")

    name, account_type = SYSTEM_ACCOUNTS[code]
    account, created = LedgerAccount.objects.get_or_create(
        owner=owner,
        code=code,
        defaults={
            "name": name,
            "account_type": account_type,
            "is_system": True,
        },
    )
    updates = {}
    if account.name != name:
        updates["name"] = name
    if account.account_type != account_type:
        updates["account_type"] = account_type
    if not account.is_system:
        updates["is_system"] = True
    if updates:
        LedgerAccount.objects.filter(id=account.id).update(**updates)
        for k, v in updates.items():
            setattr(account, k, v)
    return account


def get_or_create_gst_account(owner, direction: str, rate: Decimal | None = None) -> LedgerAccount:
    """
    Create GST ledgers in a ledger-wise manner (foundation-ready).

    Examples:
    - OUTPUT_GST_18
    - INPUT_GST_12
    """
    direction = (direction or "").strip().lower()
    if direction not in {"output", "input"}:
        raise ValueError("direction must be 'output' or 'input'")

    base_code = "OUTPUT_GST" if direction == "output" else "INPUT_GST"
    base = get_or_create_system_account(owner, base_code)

    if rate is None:
        return base

    try:
        rate_str = str(_to_decimal(rate).quantize(Decimal("0.01"))).rstrip("0").rstrip(".")
    except Exception:
        return base

    code = f"{base_code}_{rate_str}"
    name = f"{base.name} @ {rate_str}%"

    account, created = LedgerAccount.objects.get_or_create(
        owner=owner,
        code=code,
        defaults={
            "name": name,
            "account_type": base.account_type,
            "is_system": True,
        },
    )
    if not created and (account.name != name or account.account_type != base.account_type or not account.is_system):
        LedgerAccount.objects.filter(id=account.id).update(
            name=name,
            account_type=base.account_type,
            is_system=True,
        )
        account.name = name
        account.account_type = base.account_type
        account.is_system = True
    return account


def get_or_create_party_account(owner, party) -> Optional[LedgerAccount]:
    if not party:
        return None

    party_type = getattr(party, "party_type", None) or ""
    if party_type == "customer":
        acc_type = LedgerAccount.AccountType.ASSET
    elif party_type == "supplier":
        acc_type = LedgerAccount.AccountType.LIABILITY
    else:
        acc_type = LedgerAccount.AccountType.OTHER

    code = f"PARTY_{party.id}"
    name = getattr(party, "name", "") or code

    account, created = LedgerAccount.objects.get_or_create(
        owner=owner,
        code=code,
        defaults={
            "name": name,
            "account_type": acc_type,
            "is_system": False,
            "party": party,
        },
    )

    updates = {}
    if account.party_id != getattr(party, "id", None):
        updates["party"] = party
    if account.name != name:
        updates["name"] = name
    if account.account_type != acc_type:
        updates["account_type"] = acc_type
    if updates:
        LedgerAccount.objects.filter(id=account.id).update(**updates)
        for k, v in updates.items():
            setattr(account, k, v)

    return account


def get_or_create_expense_account(owner, category) -> LedgerAccount:
    if category:
        code = f"EXP_CAT_{category.id}"
        name = getattr(category, "name", "") or code
    else:
        code = "EXP_MISC"
        name = "Misc Expense"

    account, created = LedgerAccount.objects.get_or_create(
        owner=owner,
        code=code,
        defaults={
            "name": name,
            "account_type": LedgerAccount.AccountType.EXPENSE,
            "is_system": True,
        },
    )
    if not created and (account.name != name or account.account_type != LedgerAccount.AccountType.EXPENSE):
        LedgerAccount.objects.filter(id=account.id).update(
            name=name,
            account_type=LedgerAccount.AccountType.EXPENSE,
        )
        account.name = name
        account.account_type = LedgerAccount.AccountType.EXPENSE
    return account


# -----------------------------
# Posting Primitives (GL)
# -----------------------------

@dataclass(frozen=True)
class GLLine:
    account: LedgerAccount
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    description: str = ""
    party_id: int | None = None


def _validate_gl_lines(lines: Iterable[GLLine]) -> tuple[Decimal, Decimal]:
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for line in lines:
        debit = _to_decimal(line.debit)
        credit = _to_decimal(line.credit)
        if debit < 0 or credit < 0:
            raise ValueError("Debit/Credit must be non-negative")
        if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
            raise ValueError("Each GL line must be either debit or credit (non-zero).")
        total_debit += debit
        total_credit += credit

    if total_debit != total_credit:
        raise ValueError(f"Unbalanced GL lines: DR={total_debit} CR={total_credit}")
    if total_debit <= 0:
        raise ValueError("Total voucher amount must be > 0")

    return total_debit, total_credit


def sync_gl_transaction(
    *,
    owner,
    voucher_type: str,
    reference_type: str,
    reference_id: int,
    date,
    reference_no: str = "",
    narration: str = "",
    lines: list[GLLine],
) -> LedgerTransaction:
    total_debit, total_credit = _validate_gl_lines(lines)

    with transaction.atomic():
        txn, created = LedgerTransaction.objects.get_or_create(
            owner=owner,
            voucher_type=voucher_type,
            reference_type=reference_type,
            reference_id=reference_id,
            defaults={
                "date": date,
                "reference_no": reference_no or "",
                "narration": narration or "",
                "total_debit": total_debit,
                "total_credit": total_credit,
            },
        )

        if not created:
            LedgerTransaction.objects.filter(id=txn.id).update(
                date=date,
                reference_no=reference_no or "",
                narration=narration or "",
                total_debit=total_debit,
                total_credit=total_credit,
            )
            txn.date = date
            txn.reference_no = reference_no or ""
            txn.narration = narration or ""
            txn.total_debit = total_debit
            txn.total_credit = total_credit

        # Replace lines (idempotent sync)
        LedgerEntry.objects.filter(transaction=txn).delete()

        entries = []
        for idx, line in enumerate(lines, start=1):
            entries.append(
                LedgerEntry(
                    transaction=txn,
                    account=line.account,
                    party_id=line.party_id,
                    line_no=idx,
                    description=(line.description or "")[:255],
                    debit=_to_decimal(line.debit),
                    credit=_to_decimal(line.credit),
                )
            )
        LedgerEntry.objects.bulk_create(entries)

    return txn


def void_gl_transaction(*, owner, voucher_type: str, reference_type: str, reference_id: int) -> None:
    with transaction.atomic():
        LedgerTransaction.objects.filter(
            owner=owner,
            voucher_type=voucher_type,
            reference_type=reference_type,
            reference_id=reference_id,
        ).delete()


# -----------------------------
# Posting Primitives (Stock)
# -----------------------------

@dataclass(frozen=True)
class StockLine:
    product_id: int
    movement: str
    quantity: Decimal
    date: date
    reference_line_id: int | None = None
    warehouse_id: int | None = None


def sync_stock_ledger(*, owner, reference_type: str, reference_id: int, lines: list[StockLine]) -> None:
    prepared: list[StockLedger] = []
    for line in lines:
        qty = _to_decimal(line.quantity)
        if qty <= 0:
            raise ValueError("Stock quantity must be > 0")

        movement = (line.movement or "").lower()
        if movement not in {StockLedger.Movement.IN, StockLedger.Movement.OUT}:
            raise ValueError("movement must be 'in' or 'out'")

        prepared.append(
            StockLedger(
                owner=owner,
                date=line.date,
                product_id=line.product_id,
                warehouse_id=line.warehouse_id,
                movement=movement,
                quantity_in=qty if movement == StockLedger.Movement.IN else Decimal("0.00"),
                quantity_out=qty if movement == StockLedger.Movement.OUT else Decimal("0.00"),
                reference_type=reference_type,
                reference_id=reference_id,
                reference_line_id=line.reference_line_id,
            )
        )

    with transaction.atomic():
        StockLedger.objects.filter(owner=owner, reference_type=reference_type, reference_id=reference_id).delete()
        if prepared:
            StockLedger.objects.bulk_create(prepared)


def void_stock_ledger(*, owner, reference_type: str, reference_id: int) -> None:
    with transaction.atomic():
        StockLedger.objects.filter(owner=owner, reference_type=reference_type, reference_id=reference_id).delete()


# -----------------------------
# Source Document Posting (Public)
# -----------------------------

def post_invoice(invoice_id: int) -> None:
    from commerce.models import Invoice, OrderItem  # local import to avoid cycles

    invoice = (
        Invoice.objects.select_related("order", "order__party", "order__owner")
        .filter(id=invoice_id)
        .first()
    )
    if not invoice or not getattr(invoice, "order", None):
        return

    order = invoice.order
    party = getattr(order, "party", None)
    owner = getattr(order, "owner", None) or getattr(party, "owner", None)
    if not owner or not party:
        return

    order_type = (getattr(order, "order_type", "") or "").upper()
    is_sale = order_type == "SALE"
    is_purchase = order_type == "PURCHASE"
    if not (is_sale or is_purchase):
        return

    # If order_type ever changes, ensure we keep only one voucher type for this source.
    keep_voucher_type = (
        LedgerTransaction.VoucherType.SALES_INVOICE
        if is_sale
        else LedgerTransaction.VoucherType.PURCHASE_INVOICE
    )
    LedgerTransaction.objects.filter(
        owner=owner,
        reference_type="commerce.Invoice",
        reference_id=invoice.id,
        voucher_type__in=[
            LedgerTransaction.VoucherType.SALES_INVOICE,
            LedgerTransaction.VoucherType.PURCHASE_INVOICE,
        ],
    ).exclude(voucher_type=keep_voucher_type).delete()

    if getattr(invoice, "status", "") == "cancelled":
        voucher_type = keep_voucher_type
        void_gl_transaction(
            owner=owner,
            voucher_type=voucher_type,
            reference_type="commerce.Invoice",
            reference_id=invoice.id,
        )
        void_stock_ledger(owner=owner, reference_type="commerce.Invoice", reference_id=invoice.id)
        return

    total_amount = _to_decimal(getattr(invoice, "amount", None))
    tax_amount = _to_decimal(getattr(order, "tax_amount", None))
    tax_percent = _to_decimal(getattr(order, "tax_percent", None))
    gst_type = (getattr(invoice, "gst_type", "") or "").upper()

    if gst_type != "GST":
        tax_amount = Decimal("0.00")

    taxable_amount = total_amount - tax_amount
    if taxable_amount < 0:
        taxable_amount = total_amount

    party_ac = get_or_create_party_account(owner, party)
    if not party_ac:
        return

    date_val = getattr(invoice, "created_at", None)
    voucher_date = (date_val.date() if hasattr(date_val, "date") else timezone.now().date())

    if is_sale:
        sales_ac = get_or_create_system_account(owner, "SALES")
        gst_ac = get_or_create_gst_account(owner, "output", tax_percent if tax_amount > 0 else None)

        lines = [
            GLLine(account=party_ac, debit=total_amount, credit=Decimal("0.00"), party_id=party.id, description=f"{party.name}"),
            GLLine(account=sales_ac, debit=Decimal("0.00"), credit=taxable_amount, description="Sales"),
        ]
        if tax_amount > 0:
            lines.append(GLLine(account=gst_ac, debit=Decimal("0.00"), credit=tax_amount, description="Output GST"))

        sync_gl_transaction(
            owner=owner,
            voucher_type=keep_voucher_type,
            reference_type="commerce.Invoice",
            reference_id=invoice.id,
            reference_no=getattr(invoice, "number", "") or f"INV-{invoice.id}",
            date=voucher_date,
            narration=f"Sales Invoice {getattr(invoice, 'number', '')}".strip(),
            lines=lines,
        )

        # Stock OUT on sale
        items = (
            OrderItem.objects.select_related("product")
            .filter(order=order)
            .exclude(product__isnull=True)
        )
        stock_lines: list[StockLine] = []
        for it in items:
            stock_lines.append(
                    StockLine(
                        product_id=it.product_id,
                        movement=StockLedger.Movement.OUT,
                        quantity=_to_decimal(it.qty),
                        date=voucher_date,
                        reference_line_id=it.id,
                        warehouse_id=getattr(order, "warehouse_id", None),
                    )
                )
        sync_stock_ledger(owner=owner, reference_type="commerce.Invoice", reference_id=invoice.id, lines=stock_lines)

    else:
        purchase_ac = get_or_create_system_account(owner, "PURCHASE")
        gst_ac = get_or_create_gst_account(owner, "input", tax_percent if tax_amount > 0 else None)

        lines = [
            GLLine(account=purchase_ac, debit=taxable_amount, credit=Decimal("0.00"), description="Purchase"),
        ]
        if tax_amount > 0:
            lines.append(GLLine(account=gst_ac, debit=tax_amount, credit=Decimal("0.00"), description="Input GST"))
        lines.append(
            GLLine(account=party_ac, debit=Decimal("0.00"), credit=total_amount, party_id=party.id, description=f"{party.name}")
        )

        sync_gl_transaction(
            owner=owner,
            voucher_type=keep_voucher_type,
            reference_type="commerce.Invoice",
            reference_id=invoice.id,
            reference_no=getattr(invoice, "number", "") or f"PINV-{invoice.id}",
            date=voucher_date,
            narration=f"Purchase Invoice {getattr(invoice, 'number', '')}".strip(),
            lines=lines,
        )

        # Stock IN on purchase
        items = (
            OrderItem.objects.select_related("product")
            .filter(order=order)
            .exclude(product__isnull=True)
        )
        stock_lines = []
        for it in items:
            stock_lines.append(
                    StockLine(
                        product_id=it.product_id,
                        movement=StockLedger.Movement.IN,
                        quantity=_to_decimal(it.qty),
                        date=voucher_date,
                        reference_line_id=it.id,
                        warehouse_id=getattr(order, "warehouse_id", None),
                    )
                )
        sync_stock_ledger(owner=owner, reference_type="commerce.Invoice", reference_id=invoice.id, lines=stock_lines)


def post_payment(payment_id: int) -> None:
    from commerce.models import Payment

    payment = (
        Payment.objects.select_related("invoice", "invoice__order", "invoice__order__party", "invoice__order__owner")
        .filter(id=payment_id)
        .first()
    )
    if not payment or not getattr(payment, "invoice", None) or not getattr(payment.invoice, "order", None):
        return

    if getattr(payment, "is_deleted", False):
        invoice = payment.invoice
        order = invoice.order
        party = getattr(order, "party", None)
        owner = getattr(order, "owner", None) or getattr(party, "owner", None)
        if not owner:
            return
        LedgerTransaction.objects.filter(
            owner=owner,
            reference_type="commerce.Payment",
            reference_id=payment.id,
            voucher_type__in=[LedgerTransaction.VoucherType.RECEIPT, LedgerTransaction.VoucherType.PAYMENT],
        ).delete()
        return

    invoice = payment.invoice
    order = invoice.order
    party = getattr(order, "party", None)
    owner = getattr(order, "owner", None) or getattr(party, "owner", None)
    if not owner or not party:
        return

    amount = _to_decimal(getattr(payment, "amount", None))
    if amount <= 0:
        return

    method = (getattr(payment, "method", "") or "").lower()
    cash_or_bank = "CASH" if "cash" in method else "BANK"
    cash_ac = get_or_create_system_account(owner, cash_or_bank)
    party_ac = get_or_create_party_account(owner, party)
    if not party_ac:
        return

    order_type = (getattr(order, "order_type", "") or "").upper()
    is_purchase = order_type == "PURCHASE"

    ref_no = f"{getattr(invoice, 'number', '')}-PAY".strip("-") or f"PAY-{payment.id}"
    pay_date_val = getattr(payment, "created_at", None)
    pay_date = (pay_date_val.date() if hasattr(pay_date_val, "date") else timezone.now().date())

    # If order_type ever changes, ensure we keep only one voucher type for this source.
    keep_voucher_type = (
        LedgerTransaction.VoucherType.PAYMENT if is_purchase else LedgerTransaction.VoucherType.RECEIPT
    )
    LedgerTransaction.objects.filter(
        owner=owner,
        reference_type="commerce.Payment",
        reference_id=payment.id,
        voucher_type__in=[LedgerTransaction.VoucherType.RECEIPT, LedgerTransaction.VoucherType.PAYMENT],
    ).exclude(voucher_type=keep_voucher_type).delete()

    if not is_purchase:
        # Receipt: Cash/Bank DR To Party
        lines = [
            GLLine(account=cash_ac, debit=amount, credit=Decimal("0.00"), description="Receipt"),
            GLLine(account=party_ac, debit=Decimal("0.00"), credit=amount, party_id=party.id, description=f"{party.name}"),
        ]
        sync_gl_transaction(
            owner=owner,
            voucher_type=keep_voucher_type,
            reference_type="commerce.Payment",
            reference_id=payment.id,
            reference_no=ref_no,
            date=pay_date,
            narration=(getattr(payment, "note", "") or "").strip(),
            lines=lines,
        )
    else:
        # Payment: Party DR To Cash/Bank
        lines = [
            GLLine(account=party_ac, debit=amount, credit=Decimal("0.00"), party_id=party.id, description=f"{party.name}"),
            GLLine(account=cash_ac, debit=Decimal("0.00"), credit=amount, description="Payment"),
        ]
        sync_gl_transaction(
            owner=owner,
            voucher_type=keep_voucher_type,
            reference_type="commerce.Payment",
            reference_id=payment.id,
            reference_no=ref_no,
            date=pay_date,
            narration=(getattr(payment, "note", "") or "").strip(),
            lines=lines,
        )


def post_khata_transaction(txn_id: int) -> None:
    from khataapp.models import Transaction as KhataTxn

    txn = (
        KhataTxn.objects.select_related("party")
        .filter(id=txn_id)
        .first()
    )
    if not txn or not getattr(txn, "party", None):
        return

    if getattr(txn, "is_deleted", False):
        party = txn.party
        owner = getattr(party, "owner", None)
        if not owner:
            return
        LedgerTransaction.objects.filter(
            owner=owner,
            reference_type="khataapp.Transaction",
            reference_id=txn.id,
            voucher_type__in=[LedgerTransaction.VoucherType.RECEIPT, LedgerTransaction.VoucherType.PAYMENT],
        ).delete()
        return

    party = txn.party
    owner = getattr(party, "owner", None)
    if not owner:
        return

    amount = _to_decimal(getattr(txn, "amount", None))
    if amount <= 0:
        return

    mode = (getattr(txn, "txn_mode", "") or "").lower()
    cash_or_bank = "CASH" if mode == "cash" else "BANK"
    cash_ac = get_or_create_system_account(owner, cash_or_bank)
    party_ac = get_or_create_party_account(owner, party)
    if not party_ac:
        return

    txn_type = (getattr(txn, "txn_type", "") or "").lower()
    ref_no = f"TXN-{txn.id}"
    txn_date = getattr(txn, "date", None) or timezone.now().date()
    narration = (getattr(txn, "notes", "") or "").strip()

    keep_voucher_type = (
        LedgerTransaction.VoucherType.RECEIPT if txn_type == "credit" else LedgerTransaction.VoucherType.PAYMENT
    )
    LedgerTransaction.objects.filter(
        owner=owner,
        reference_type="khataapp.Transaction",
        reference_id=txn.id,
        voucher_type__in=[LedgerTransaction.VoucherType.RECEIPT, LedgerTransaction.VoucherType.PAYMENT],
    ).exclude(voucher_type=keep_voucher_type).delete()

    if txn_type == "credit":
        # Receipt: Cash/Bank DR To Party
        lines = [
            GLLine(account=cash_ac, debit=amount, credit=Decimal("0.00"), description="Receipt"),
            GLLine(account=party_ac, debit=Decimal("0.00"), credit=amount, party_id=party.id, description=f"{party.name}"),
        ]
        sync_gl_transaction(
            owner=owner,
            voucher_type=keep_voucher_type,
            reference_type="khataapp.Transaction",
            reference_id=txn.id,
            reference_no=ref_no,
            date=txn_date,
            narration=narration,
            lines=lines,
        )
    elif txn_type == "debit":
        # Payment: Party DR To Cash/Bank
        lines = [
            GLLine(account=party_ac, debit=amount, credit=Decimal("0.00"), party_id=party.id, description=f"{party.name}"),
            GLLine(account=cash_ac, debit=Decimal("0.00"), credit=amount, description="Payment"),
        ]
        sync_gl_transaction(
            owner=owner,
            voucher_type=keep_voucher_type,
            reference_type="khataapp.Transaction",
            reference_id=txn.id,
            reference_no=ref_no,
            date=txn_date,
            narration=narration,
            lines=lines,
        )


def post_expense(expense_id: int) -> None:
    from accounts.models import Expense

    expense = Expense.objects.select_related("category", "created_by").filter(id=expense_id).first()
    if not expense or not getattr(expense, "created_by", None):
        return

    owner = expense.created_by
    amount = _to_decimal(getattr(expense, "amount_paid", None))
    if amount <= 0:
        return

    expense_ac = get_or_create_expense_account(owner, getattr(expense, "category", None))
    cash_ac = get_or_create_system_account(owner, "CASH")

    exp_date = getattr(expense, "expense_date", None) or timezone.now().date()
    ref_no = getattr(expense, "expense_number", "") or f"EXP-{expense.id}"
    narration = (getattr(expense, "description", "") or "").strip()

    lines = [
        GLLine(account=expense_ac, debit=amount, credit=Decimal("0.00"), description="Expense"),
        GLLine(account=cash_ac, debit=Decimal("0.00"), credit=amount, description="Cash"),
    ]
    sync_gl_transaction(
        owner=owner,
        voucher_type=LedgerTransaction.VoucherType.EXPENSE,
        reference_type="accounts.Expense",
        reference_id=expense.id,
        reference_no=ref_no,
        date=exp_date,
        narration=narration,
        lines=lines,
    )


def post_supplier_payment(supplier_payment_id: int) -> None:
    from khataapp.models import SupplierPayment

    sp = (
        SupplierPayment.objects.select_related("supplier", "order", "order__owner")
        .filter(id=supplier_payment_id)
        .first()
    )
    if not sp or not getattr(sp, "supplier", None):
        return

    party = sp.supplier
    owner = getattr(sp.order, "owner", None) or getattr(party, "owner", None)
    if not owner:
        return

    amount = _to_decimal(getattr(sp, "amount", None))
    if amount <= 0:
        return

    mode = (getattr(sp, "payment_mode", "") or "").lower()
    cash_or_bank = "CASH" if mode == "cash" else "BANK"
    cash_ac = get_or_create_system_account(owner, cash_or_bank)
    party_ac = get_or_create_party_account(owner, party)
    if not party_ac:
        return

    sp_date = getattr(sp, "payment_date", None) or timezone.now().date()
    ref_no = f"SUPP-PAY-{sp.id}"
    narration = (getattr(sp, "notes", "") or "").strip()

    lines = [
        GLLine(account=party_ac, debit=amount, credit=Decimal("0.00"), party_id=party.id, description=f"{party.name}"),
        GLLine(account=cash_ac, debit=Decimal("0.00"), credit=amount, description="Payment"),
    ]

    sync_gl_transaction(
        owner=owner,
        voucher_type=LedgerTransaction.VoucherType.PAYMENT,
        reference_type="khataapp.SupplierPayment",
        reference_id=sp.id,
        reference_no=ref_no,
        date=sp_date,
        narration=narration,
        lines=lines,
    )


def post_stock_transfer(transfer_id: int) -> None:
    transfer = (
        StockTransfer.objects.select_related("from_warehouse", "to_warehouse", "owner")
        .prefetch_related("items")
        .filter(id=transfer_id)
        .first()
    )
    if not transfer:
        return

    owner = transfer.owner
    if transfer.status != StockTransfer.Status.POSTED:
        void_stock_ledger(owner=owner, reference_type="ledger.StockTransfer", reference_id=transfer.id)
        return

    lines: list[StockLine] = []
    for item in transfer.items.all():
        qty = _to_decimal(getattr(item, "quantity", None))
        if qty <= 0:
            continue
        # OUT from source
        lines.append(
            StockLine(
                product_id=item.product_id,
                movement=StockLedger.Movement.OUT,
                quantity=qty,
                date=transfer.date,
                reference_line_id=item.id,
                warehouse_id=transfer.from_warehouse_id,
            )
        )
        # IN to destination
        lines.append(
            StockLine(
                product_id=item.product_id,
                movement=StockLedger.Movement.IN,
                quantity=qty,
                date=transfer.date,
                reference_line_id=item.id,
                warehouse_id=transfer.to_warehouse_id,
            )
        )

    if not lines:
        return
    sync_stock_ledger(owner=owner, reference_type="ledger.StockTransfer", reference_id=transfer.id, lines=lines)


def post_journal_voucher(voucher_id: int) -> None:
    voucher = (
        JournalVoucher.objects.select_related("owner")
        .prefetch_related("lines", "lines__account")
        .filter(id=voucher_id)
        .first()
    )
    if not voucher:
        return

    owner = voucher.owner
    if voucher.status != JournalVoucher.Status.POSTED:
        void_gl_transaction(
            owner=owner,
            voucher_type=LedgerTransaction.VoucherType.JOURNAL,
            reference_type="ledger.JournalVoucher",
            reference_id=voucher.id,
        )
        return

    lines: list[GLLine] = []
    for line in voucher.lines.all():
        lines.append(
            GLLine(
                account=line.account,
                debit=_to_decimal(line.debit),
                credit=_to_decimal(line.credit),
                description=line.description,
                party_id=line.party_id,
            )
        )

    sync_gl_transaction(
        owner=owner,
        voucher_type=LedgerTransaction.VoucherType.JOURNAL,
        reference_type="ledger.JournalVoucher",
        reference_id=voucher.id,
        reference_no=f"JV-{voucher.id}",
        date=voucher.date,
        narration=voucher.narration,
        lines=lines,
    )


def post_return_note(note_id: int) -> None:
    from ledger.models import ReturnNote, ReturnNoteItem

    note = (
        ReturnNote.objects.select_related(
            "owner",
            "invoice",
            "invoice__order",
            "invoice__order__party",
        )
        .prefetch_related("items", "items__product")
        .filter(id=note_id)
        .first()
    )
    if not note or not getattr(note, "invoice", None) or not getattr(note.invoice, "order", None):
        return

    owner = note.owner
    invoice = note.invoice
    order = invoice.order
    party = getattr(order, "party", None)
    if not owner or not party:
        return

    # Only POSTED notes generate entries; draft/cancelled remove entries
    if note.status != ReturnNote.Status.POSTED:
        LedgerTransaction.objects.filter(
            owner=owner,
            reference_type="ledger.ReturnNote",
            reference_id=note.id,
            voucher_type__in=[
                LedgerTransaction.VoucherType.CREDIT_NOTE,
                LedgerTransaction.VoucherType.DEBIT_NOTE,
            ],
        ).delete()
        void_stock_ledger(owner=owner, reference_type="ledger.ReturnNote", reference_id=note.id)
        return

    order_type = (getattr(order, "order_type", "") or "").upper()
    is_sale = order_type == "SALE"
    is_purchase = order_type == "PURCHASE"
    if not (is_sale or is_purchase):
        return

    note_type = (getattr(note, "note_type", "") or "").lower()
    if is_sale and note_type != ReturnNote.NoteType.CREDIT:
        note_type = ReturnNote.NoteType.CREDIT
    if is_purchase and note_type != ReturnNote.NoteType.DEBIT:
        note_type = ReturnNote.NoteType.DEBIT

    gst_type = (getattr(invoice, "gst_type", "") or "").upper()
    tax_percent = _to_decimal(getattr(order, "tax_percent", None))

    taxable_amount = _to_decimal(getattr(note, "taxable_amount", None))
    tax_amount = _to_decimal(getattr(note, "tax_amount", None))
    total_amount = _to_decimal(getattr(note, "total_amount", None))

    if gst_type != "GST":
        tax_amount = Decimal("0.00")
        total_amount = taxable_amount

    party_ac = get_or_create_party_account(owner, party)
    if not party_ac:
        return

    voucher_date = getattr(note, "date", None) or timezone.now().date()

    items = list(note.items.all())
    stock_lines: list[StockLine] = []
    for it in items:
        qty = _to_decimal(getattr(it, "quantity", None))
        if qty <= 0:
            continue
        stock_lines.append(
            StockLine(
                product_id=it.product_id,
                movement=StockLedger.Movement.IN if is_sale else StockLedger.Movement.OUT,
                quantity=qty,
                date=voucher_date,
                reference_line_id=it.id,
                warehouse_id=getattr(order, "warehouse_id", None),
            )
        )

    if is_sale:
        sales_ac = get_or_create_system_account(owner, "SALES")
        gst_ac = get_or_create_gst_account(owner, "output", tax_percent if tax_amount > 0 else None)
        lines = [
            GLLine(account=sales_ac, debit=taxable_amount, credit=Decimal("0.00"), description="Sales Return"),
        ]
        if tax_amount > 0:
            lines.append(GLLine(account=gst_ac, debit=tax_amount, credit=Decimal("0.00"), description="Output GST Reversal"))
        lines.append(
            GLLine(account=party_ac, debit=Decimal("0.00"), credit=total_amount, party_id=party.id, description=f"{party.name}")
        )

        sync_gl_transaction(
            owner=owner,
            voucher_type=LedgerTransaction.VoucherType.CREDIT_NOTE,
            reference_type="ledger.ReturnNote",
            reference_id=note.id,
            reference_no=f"CN-{note.id}",
            date=voucher_date,
            narration=(getattr(note, "narration", "") or "").strip() or f"Credit Note for {getattr(invoice, 'number', '')}".strip(),
            lines=lines,
        )

    else:
        purchase_ac = get_or_create_system_account(owner, "PURCHASE")
        gst_ac = get_or_create_gst_account(owner, "input", tax_percent if tax_amount > 0 else None)
        lines = [
            GLLine(account=party_ac, debit=total_amount, credit=Decimal("0.00"), party_id=party.id, description=f"{party.name}"),
        ]
        lines.append(GLLine(account=purchase_ac, debit=Decimal("0.00"), credit=taxable_amount, description="Purchase Return"))
        if tax_amount > 0:
            lines.append(GLLine(account=gst_ac, debit=Decimal("0.00"), credit=tax_amount, description="Input GST Reversal"))

        sync_gl_transaction(
            owner=owner,
            voucher_type=LedgerTransaction.VoucherType.DEBIT_NOTE,
            reference_type="ledger.ReturnNote",
            reference_id=note.id,
            reference_no=f"DN-{note.id}",
            date=voucher_date,
            narration=(getattr(note, "narration", "") or "").strip() or f"Debit Note for {getattr(invoice, 'number', '')}".strip(),
            lines=lines,
        )

    if stock_lines:
        sync_stock_ledger(owner=owner, reference_type="ledger.ReturnNote", reference_id=note.id, lines=stock_lines)


# -----------------------------
# Signal-friendly scheduling
# -----------------------------

def schedule_on_commit(func, *args, **kwargs) -> None:
    """
    Ensure posting runs after DB commit.

    Signals can fire inside an outer atomic() block; on_commit makes sure we see consistent data.
    """
    def _run():
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception("ERP posting callback failed: %s", getattr(func, "__name__", str(func)))

    try:
        transaction.on_commit(_run)
    except Exception:
        # If there is no active transaction (or on_commit unavailable), run immediately.
        _run()
