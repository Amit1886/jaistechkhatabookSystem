from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from django.utils import timezone

from accounts.models import Expense, ExpenseCategory
from bank_import.statement_parser import BankTxn
from khataapp.models import Party, Transaction as KhataTransaction


@dataclass(frozen=True)
class MapResult:
    ok: bool
    created_type: str
    created_id: Optional[int]
    note: str = ""


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def _find_party(owner, description: str) -> Optional[Party]:
    description = (description or "").strip()
    if not description:
        return None
    # naive: try matching party name substring
    return Party.objects.filter(owner=owner, name__icontains=description[:24]).order_by("name").first()


def _get_or_create_expense_category(owner, name: str) -> ExpenseCategory:
    name = (name or "").strip() or "Bank Import"
    cat = ExpenseCategory.objects.filter(created_by=owner, name__iexact=name).first()
    if cat:
        return cat
    return ExpenseCategory.objects.create(created_by=owner, name=name)


def map_bank_txn_to_entries(owner, txn: BankTxn, *, mapping_rules: dict[str, Any] | None = None) -> MapResult:
    """
    Creates:
    - Receipt (khataapp.Transaction credit) for credits
    - Payment (khataapp.Transaction debit) for debits
    - Expense (accounts.Expense) if mapped as expense

    mapping_rules (optional):
    {
      "expenses": [
         {"pattern": "diesel", "category": "Fuel"}
      ]
    }
    """
    rules = mapping_rules or {}
    desc = (txn.description or "").strip()

    # Expense mapping first (debits)
    if txn.debit and txn.debit > 0:
        for rule in (rules.get("expenses") or []):
            try:
                pat = str(rule.get("pattern") or "").strip()
                if not pat:
                    continue
                if re.search(pat, desc, flags=re.IGNORECASE):
                    cat = _get_or_create_expense_category(owner, str(rule.get("category") or "Bank Import"))
                    exp = Expense.objects.create(
                        expense_number=f"EXP-BANK-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                        expense_date=txn.date or timezone.localdate(),
                        category=cat,
                        description=desc or "Bank import expense",
                        amount_paid=txn.debit,
                        created_by=owner,
                    )
                    return MapResult(ok=True, created_type="accounts.Expense", created_id=exp.id, note="Expense mapped")
            except Exception:
                continue

    # Receipts/Payments as Khata Transactions
    party = _find_party(owner, desc) or Party.objects.filter(owner=owner, name__iexact="Bank").first()
    if not party:
        party = Party.objects.create(owner=owner, name="Bank", party_type="supplier")

    if txn.credit and txn.credit > 0:
        t = KhataTransaction.objects.create(
            party=party,
            txn_type="credit",
            txn_mode="bank",
            amount=txn.credit,
            date=txn.date or timezone.localdate(),
            notes=f"Bank import: {desc}"[:500],
            voucher_type="bank_import",
            created_by=owner,
        )
        return MapResult(ok=True, created_type="khataapp.Transaction", created_id=t.id, note="Receipt created")

    if txn.debit and txn.debit > 0:
        t = KhataTransaction.objects.create(
            party=party,
            txn_type="debit",
            txn_mode="bank",
            amount=txn.debit,
            date=txn.date or timezone.localdate(),
            notes=f"Bank import: {desc}"[:500],
            voucher_type="bank_import",
            created_by=owner,
        )
        return MapResult(ok=True, created_type="khataapp.Transaction", created_id=t.id, note="Payment created")

    return MapResult(ok=False, created_type="", created_id=None, note="Zero amount")


def classify_bank_txn(txn: BankTxn, *, mapping_rules: dict[str, Any] | None = None) -> str:
    """
    Returns a user-friendly action label without writing to DB.
    """
    rules = mapping_rules or {}
    desc = (txn.description or "").strip()

    if txn.debit and txn.debit > 0:
        for rule in (rules.get("expenses") or []):
            try:
                pat = str(rule.get("pattern") or "").strip()
                if pat and re.search(pat, desc, flags=re.IGNORECASE):
                    return f"Expense ({rule.get('category') or 'Bank Import'})"
            except Exception:
                continue
        return "Payment"

    if txn.credit and txn.credit > 0:
        return "Receipt"

    return "Skip"
