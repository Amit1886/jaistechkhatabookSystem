from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional


@dataclass(frozen=True)
class ParsedCommand:
    intent: str
    confidence: float
    payload: dict[str, Any]
    raw: str


_WS = re.compile(r"\s+")


def _to_decimal(value: str) -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return Decimal("0.00")


def _norm(text: str) -> str:
    text = (text or "").strip()
    text = _WS.sub(" ", text)
    return text


def _extract_amount(text: str) -> Optional[Decimal]:
    # Prefer last number as amount: "expense diesel 500" or "receive payment 5000 from X"
    m = re.findall(r"(?<!\w)(\d+(?:\.\d{1,2})?)(?!\w)", text)
    if not m:
        return None
    return _to_decimal(m[-1])


def parse_accounting_command(text: str) -> Optional[ParsedCommand]:
    """
    Parse WhatsApp/Voice accounting commands into a structured intent.

    Supported examples:
    - sale 5 ice cream cone 250
    - expense diesel 500
    - receive payment 5000 from Ram Traders
    """
    raw = _norm(text)
    if not raw:
        return None

    low = raw.lower()

    # Sale: "sale <qty> <item name> <price>"
    if low.startswith(("sale ", "add sale ")):
        # Strip "add "
        low2 = low[4:] if low.startswith("add ") else low
        parts = low2.split(" ")
        # parts[0] = "sale"
        qty = None
        unit_price = None
        if len(parts) >= 2:
            try:
                qty = int(parts[1])
            except Exception:
                qty = None
        amount = _extract_amount(raw)
        if amount is not None and qty:
            try:
                unit_price = (amount / Decimal(qty)).quantize(Decimal("0.01"))
            except Exception:
                unit_price = None

        # item name: everything between qty and last amount token (best-effort)
        name = ""
        if qty is not None:
            # remove leading "sale {qty}"
            remainder = raw.split(" ", 2)[2] if len(raw.split(" ", 2)) == 3 else ""
            if amount is not None:
                # drop the last number occurrence
                name = re.sub(r"(?<!\w)\d+(?:\.\d{1,2})?(?!\w)\s*$", "", remainder).strip()
            else:
                name = remainder.strip()

        payload = {
            "qty": qty or 1,
            "item_name": name or "",
            "amount": str(amount) if amount is not None else "",
            "unit_price": str(unit_price) if unit_price is not None else "",
        }
        return ParsedCommand(intent="sale", confidence=0.75, payload=payload, raw=raw)

    # Expense: "expense <desc> <amount>"
    if low.startswith(("expense ", "add expense ")):
        low2 = low[4:] if low.startswith("add ") else low
        amount = _extract_amount(raw)
        desc = low2[len("expense ") :].strip()
        if amount is not None:
            desc = re.sub(r"(?<!\w)\d+(?:\.\d{1,2})?(?!\w)\s*$", "", desc).strip()
        payload = {"description": desc, "amount": str(amount or Decimal("0.00"))}
        return ParsedCommand(intent="expense", confidence=0.8, payload=payload, raw=raw)

    # Receive payment: "receive payment <amount> from <party>"
    if "receive" in low and "payment" in low:
        amount = _extract_amount(raw)
        party = ""
        m = re.search(r"\bfrom\b\s+(.+)$", raw, flags=re.IGNORECASE)
        if m:
            party = m.group(1).strip()
        payload = {"amount": str(amount or Decimal("0.00")), "party_name": party}
        return ParsedCommand(intent="receive_payment", confidence=0.78, payload=payload, raw=raw)

    # Pay supplier: "pay <amount> to <party>" / "payment <amount> to <party>"
    if low.startswith(("pay ", "payment ")):
        amount = _extract_amount(raw)
        party = ""
        m = re.search(r"\bto\b\s+(.+)$", raw, flags=re.IGNORECASE)
        if m:
            party = m.group(1).strip()
        payload = {"amount": str(amount or Decimal("0.00")), "party_name": party}
        return ParsedCommand(intent="make_payment", confidence=0.7, payload=payload, raw=raw)

    return None

