from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from ledger.models import LedgerEntry, LedgerTransaction, Receipt


@dataclass(frozen=True)
class ReceiptRow:
    sno: int
    dc: str
    party: str
    amount: Decimal
    narration: str


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def _short(text: str, limit: int = 80) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _detect_gst(*, reference_type: str, reference_id: int) -> bool:
    if reference_type != "commerce.Invoice":
        return False
    try:
        from commerce.models import Invoice  # local import

        invoice = Invoice.objects.filter(id=reference_id).only("gst_type").first()
        return bool(invoice and (invoice.gst_type or "").upper() == "GST")
    except Exception:
        return False


def build_receipt_context(
    *,
    owner,
    reference_type: str,
    reference_id: int,
    voucher_type: Optional[str] = None,
    kind: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    # Fallback: legacy cashbook transactions may not post to GL.
    # Example reference_type: "khataapp.Transaction"
    if reference_type == "khataapp.Transaction":
        try:
            from khataapp.models import Transaction  # local import

            t = (
                Transaction.objects.select_related("party")
                .filter(id=reference_id, party__owner=owner)
                .first()
            )
            if not t:
                return None

            amount = _to_decimal(getattr(t, "amount", None))
            mode_label = ""
            try:
                mode_label = t.get_txn_mode_display()  # type: ignore[attr-defined]
            except Exception:
                mode_label = getattr(t, "txn_mode", "") or ""
            cash_account = mode_label or "Cash/Bank"

            txn_type = (getattr(t, "txn_type", "") or "").lower()
            is_receipt = txn_type == "credit"

            notes = getattr(t, "notes", "") or ""
            # Make template compatible with LedgerTransaction fields.
            t.narration = notes  # type: ignore[attr-defined]

            # Two-line, balanced rows (double entry style for printing).
            if is_receipt:
                rows = [
                    ReceiptRow(sno=1, dc="DR", party=cash_account, amount=amount, narration=_short(notes, 90)),
                    ReceiptRow(sno=2, dc="CR", party=getattr(t.party, "name", "") or "Party", amount=amount, narration=_short(notes, 90)),
                ]
                voucher_type_resolved = voucher_type or "Receipt"
            else:
                rows = [
                    ReceiptRow(sno=1, dc="DR", party=getattr(t.party, "name", "") or "Party", amount=amount, narration=_short(notes, 90)),
                    ReceiptRow(sno=2, dc="CR", party=cash_account, amount=amount, narration=_short(notes, 90)),
                ]
                voucher_type_resolved = voucher_type or "Payment"

            gst_enabled = (getattr(t, "gst_type", "") or "").lower() == "gst"
            reference_no = f"TXN-{t.id}"
            resolved_kind = Receipt.Kind.PAYMENT
            if kind:
                valid_kinds = {k for k, _ in Receipt.Kind.choices}
                if kind in valid_kinds:
                    resolved_kind = kind

            return {
                "txn": t,
                "rows": rows,
                "gst_enabled": gst_enabled,
                "reference_type": reference_type,
                "reference_id": reference_id,
                "reference_no": reference_no,
                "voucher_type": voucher_type_resolved,
                "kind": resolved_kind,
                "total_debit": amount,
                "total_credit": amount,
            }
        except Exception:
            return None

    qs = LedgerTransaction.objects.filter(
        owner=owner,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    if voucher_type:
        qs = qs.filter(voucher_type=voucher_type)

    txn = (
        qs.order_by("-date", "-id")
        .prefetch_related("entries", "entries__account", "entries__party")
        .first()
    )
    if not txn:
        return None

    entries: list[LedgerEntry] = list(
        txn.entries.select_related("account", "party").all().order_by("line_no", "id")
    )

    rows: list[ReceiptRow] = []
    for idx, e in enumerate(entries, start=1):
        amount = _to_decimal(e.debit if e.debit and e.debit > 0 else e.credit)
        dc = "DR" if e.debit and e.debit > 0 else "CR"
        party_name = ""
        if getattr(e, "party", None):
            party_name = getattr(e.party, "name", "") or ""
        if not party_name:
            party_name = getattr(e.account, "name", "") or getattr(e.account, "code", "") or "-"

        narration = e.description or txn.narration or ""
        rows.append(
            ReceiptRow(
                sno=idx,
                dc=dc,
                party=party_name,
                amount=amount,
                narration=_short(narration, 90),
            )
        )

    gst_enabled = _detect_gst(reference_type=reference_type, reference_id=reference_id)
    reference_no = getattr(txn, "reference_no", "") or str(reference_id)

    resolved_kind = Receipt.Kind.NOT_APPLICABLE
    vt = (getattr(txn, "voucher_type", "") or "").lower()
    if "invoice" in vt:
        resolved_kind = Receipt.Kind.INVOICE
    elif vt == "receipt":
        resolved_kind = Receipt.Kind.PAYMENT
    elif vt == "payment":
        resolved_kind = Receipt.Kind.PAYMENT
    elif vt == "journal":
        resolved_kind = Receipt.Kind.VOUCHER
    elif vt in {"credit_note", "debit_note"}:
        resolved_kind = Receipt.Kind.VOUCHER

    if kind:
        valid_kinds = {k for k, _ in Receipt.Kind.choices}
        if kind in valid_kinds:
            resolved_kind = kind

    receipt_no = reference_no or f"RCP-{txn.id}"
    try:
        Receipt.objects.update_or_create(
            owner=owner,
            reference_type=reference_type,
            reference_id=reference_id,
            voucher_type=getattr(txn, "voucher_type", "") or "",
            defaults={
                "kind": resolved_kind,
                "receipt_no": receipt_no,
                "gst_enabled": gst_enabled,
                "gl_transaction": txn,
            },
        )
    except Exception:
        # Receipt persistence must never break rendering.
        pass

    return {
        "txn": txn,
        "rows": rows,
        "gst_enabled": gst_enabled,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "reference_no": reference_no,
        "voucher_type": getattr(txn, "voucher_type", ""),
        "kind": resolved_kind,
        "total_debit": getattr(txn, "total_debit", Decimal("0.00")),
        "total_credit": getattr(txn, "total_credit", Decimal("0.00")),
    }
