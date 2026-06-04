from __future__ import annotations

import re
from decimal import Decimal

from django.utils import timezone

from superapp.models import ExpenseApproval, ExpenseScan, OCRResult, VendorMatch

GSTIN_RE = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
AMOUNT_RE = re.compile(r"(?:total|amount|grand total)[:\s₹rs.]*([0-9,]+(?:\.[0-9]{1,2})?)", re.I)
INVOICE_RE = re.compile(r"(?:invoice|bill)\s*(?:no|number|#)?[:\s-]*([A-Z0-9/-]+)", re.I)
DATE_RE = re.compile(r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")


def parse_receipt_text(text: str) -> dict:
    text = text or ""
    gstin = GSTIN_RE.search(text)
    amount = AMOUNT_RE.search(text)
    invoice = INVOICE_RE.search(text)
    date = DATE_RE.search(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return {
        "vendor_name": lines[0][:180] if lines else "",
        "gstin": gstin.group(0) if gstin else "",
        "invoice_number": invoice.group(1)[:100] if invoice else "",
        "invoice_date_text": date.group(1) if date else "",
        "amount": Decimal((amount.group(1).replace(",", "") if amount else "0") or "0"),
        "raw_lines": lines[:80],
    }


def process_expense_scan(scan: ExpenseScan, *, raw_text: str = "") -> ExpenseScan:
    parsed = parse_receipt_text(raw_text)
    parsed_payload = {**parsed, "amount": str(parsed.get("amount") or "0")}
    duplicate = None
    if parsed.get("gstin") and parsed.get("invoice_number"):
        duplicate = (
            ExpenseScan.objects.filter(gstin=parsed["gstin"], invoice_number=parsed["invoice_number"])
            .exclude(pk=scan.pk)
            .order_by("-created_at")
            .first()
        )
    scan.vendor_name = parsed.get("vendor_name") or scan.vendor_name
    scan.gstin = parsed.get("gstin") or scan.gstin
    scan.invoice_number = parsed.get("invoice_number") or scan.invoice_number
    scan.amount = parsed.get("amount") or scan.amount
    scan.duplicate_of = duplicate
    scan.status = "duplicate" if duplicate else "parsed"
    scan.metadata = {**(scan.metadata or {}), "parsed_at": timezone.now().isoformat()}
    scan.save()
    OCRResult.objects.update_or_create(
        expense_scan=scan,
        defaults={"raw_text": raw_text, "parsed_payload": parsed_payload, "confidence": Decimal("75.00") if raw_text else 0},
    )
    if scan.vendor_name:
        VendorMatch.objects.create(expense_scan=scan, vendor_name=scan.vendor_name, confidence=Decimal("80.00"), metadata={"source": "ocr"})
    ExpenseApproval.objects.get_or_create(expense_scan=scan, level=1, defaults={"status": "pending"})
    return scan
