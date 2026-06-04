from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedInvoice:
    supplier_name: str
    invoice_no: str
    invoice_date: str
    items: list[dict[str, Any]]
    totals: dict[str, Any]
    confidence: float
    raw_text: str = ""


_WS = re.compile(r"\s+")
_NUM_RE = re.compile(r"(?<!\w)(\d+(?:,\d{2,3})*(?:\.\d{1,2})?)(?!\w)")
_PCT_RE = re.compile(r"(?<!\w)(\d{1,2}(?:\.\d{1,2})?)\s*%(?!\w)")
_GST_SLABS = {Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")}


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return Decimal("0.00")


def _norm(text: str) -> str:
    text = (text or "").strip()
    return _WS.sub(" ", text)


def _maybe_gst_slab(value: Decimal) -> Optional[Decimal]:
    try:
        n = int(value)
    except Exception:
        return None
    v = Decimal(str(n))
    if v in _GST_SLABS:
        return v
    return None


def _extract_numbers(text: str) -> list[Decimal]:
    return [_to_decimal(tok) for tok in _NUM_RE.findall(text or "")]


def _extract_gst_rate_from_line(line: str) -> Optional[Decimal]:
    low = (line or "").lower()
    pct_tokens = [_to_decimal(x) for x in _PCT_RE.findall(line or "")]
    slab_tokens = [s for s in (_maybe_gst_slab(p) for p in pct_tokens) if s is not None]
    if not slab_tokens:
        return None
    if any(k in low for k in ("gst", "igst", "cgst", "sgst")):
        # Prefer a slab when tax keywords present.
        return slab_tokens[0]
    # Otherwise, best-effort: keep a common slab but avoid catching discount % often found as 5/10.
    for v in slab_tokens:
        if v in {Decimal("12"), Decimal("18"), Decimal("28")}:
            return v
    return slab_tokens[0]


def _extract_gst_rate_overall(text: str) -> Optional[Decimal]:
    raw = text or ""
    # IGST: "IGST 18%" etc.
    m = re.search(r"\bigst\b[^0-9%]{0,30}(\d{1,2}(?:\.\d{1,2})?)\s*%", raw, flags=re.IGNORECASE)
    if m:
        val = _maybe_gst_slab(_to_decimal(m.group(1)))
        if val is not None:
            return val

    # CGST + SGST (often split): "CGST 9%" + "SGST 9%" => 18%
    m1 = re.search(r"\bcgst\b[^0-9%]{0,30}(\d{1,2}(?:\.\d{1,2})?)\s*%", raw, flags=re.IGNORECASE)
    m2 = re.search(r"\bsgst\b[^0-9%]{0,30}(\d{1,2}(?:\.\d{1,2})?)\s*%", raw, flags=re.IGNORECASE)
    if m1 and m2:
        try:
            total = _to_decimal(m1.group(1)) + _to_decimal(m2.group(1))
        except Exception:
            total = Decimal("0")
        slab = _maybe_gst_slab(total)
        if slab is not None:
            return slab

    # Fallback: pick the first slab-like percent in the document.
    for tok in _PCT_RE.findall(raw):
        slab = _maybe_gst_slab(_to_decimal(tok))
        if slab is not None:
            return slab
    return None


def _best_effort_regex_parse(text: str) -> ParsedInvoice:
    """
    Heuristic parser (works for simple invoices).
    For higher accuracy, plug an LLM JSON extraction step later.
    """
    raw = text or ""
    t = raw
    supplier = ""
    inv_no = ""
    inv_date = ""

    # Common patterns
    m = re.search(r"(?:Invoice\s*No\.?|Inv\s*No\.?)\s*[:#]?\s*([A-Za-z0-9\-\/]+)", t, flags=re.IGNORECASE)
    if m:
        inv_no = m.group(1).strip()
    m = re.search(r"(?:Invoice\s*Date|Date)\s*[:#]?\s*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})", t, flags=re.IGNORECASE)
    if m:
        inv_date = m.group(1).strip()

    # Supplier: first non-empty line, skipping common headers
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if lines:
        for ln in lines:
            low_ln = ln.lower()
            if any(k in low_ln for k in ("tax invoice", "invoice", "gstin", "bill to", "ship to")):
                continue
            supplier = ln[:120]
            break
        if not supplier:
            supplier = lines[0][:120]

    items: list[dict[str, Any]] = []
    overall_gst_rate = _extract_gst_rate_overall(raw)
    stop_words = ("grand total", "total", "subtotal", "sub total", "gstin", "invoice", "cgst", "sgst", "igst", "tax")

    # Best-effort line item guess: "<name> <qty> <rate> <amount> [gst%]"
    for ln in lines:
        ln2 = _norm(ln)
        low_ln2 = ln2.lower()
        if any(w in low_ln2 for w in stop_words):
            continue

        nums = _extract_numbers(ln2)
        if len(nums) < 2:
            continue

        gst_rate = _extract_gst_rate_from_line(ln2) or overall_gst_rate

        # If the line ends with a GST slab like "18%", drop that token from numeric candidates.
        end_pct = re.search(r"(\d{1,2}(?:\.\d{1,2})?)\s*%\s*$", ln2)
        if end_pct and gst_rate is not None:
            try:
                end_v = _to_decimal(end_pct.group(1))
            except Exception:
                end_v = Decimal("0")
            if _maybe_gst_slab(end_v) == gst_rate and nums and nums[-1] == end_v:
                nums = nums[:-1]

        # Common invoices include HSN as a leading numeric column.
        if len(nums) >= 3:
            try:
                first_int = int(nums[0])
                if nums[0] == Decimal(str(first_int)) and first_int >= 1000 and len(str(first_int)) in {4, 6, 8}:
                    # If the next number looks like a quantity, drop HSN.
                    if nums[1] <= Decimal("1000"):
                        nums = nums[1:]
            except Exception:
                pass

        if len(nums) < 2:
            continue

        qty = nums[0]
        amount = nums[-1]
        if qty <= 0 or amount <= 0:
            continue

        if len(nums) >= 3:
            rate = nums[1]
        else:
            try:
                rate = (amount / qty).quantize(Decimal("0.01"))
            except Exception:
                rate = Decimal("0.00")

        name = _NUM_RE.sub("", ln2)
        name = name.replace("%", " ")
        name = re.sub(r"\b(HSN|SAC)\b", "", name, flags=re.IGNORECASE)
        name = _norm(name).strip(" -|:\t")
        if not name or len(name) < 2:
            continue

        item: dict[str, Any] = {
            "name": name[:140],
            "qty": str(qty),
            "rate": str(rate.quantize(Decimal("0.01"))),
            "amount": str(amount.quantize(Decimal("0.01"))),
        }
        if gst_rate is not None:
            item["gst_rate"] = str(gst_rate.quantize(Decimal("0.01")))
        items.append(item)

    totals = {"total": ""}
    m = re.search(r"(?:Grand\s*Total|Total)\s*[:]?[\s₹Rs.]*?(\d+(?:,\d{2,3})*(?:\.\d{1,2})?)", raw, flags=re.IGNORECASE)
    if m:
        totals["total"] = str(_to_decimal(m.group(1)))
    if overall_gst_rate is not None:
        totals["gst_rate"] = str(overall_gst_rate.quantize(Decimal("0.01")))

    confidence = 0.35 if items else 0.2
    return ParsedInvoice(
        supplier_name=supplier,
        invoice_no=inv_no,
        invoice_date=inv_date,
        items=items,
        totals=totals,
        confidence=confidence,
        raw_text=raw,
    )


def parse_invoice_text(text: str) -> ParsedInvoice:
    return _best_effort_regex_parse(text)


def parse_invoice_text_llm(text: str) -> Optional[ParsedInvoice]:
    """
    Optional: LLM JSON extraction step.
    Returns None if unavailable.
    """
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI()
    except Exception:
        return None

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": "Extract structured invoice data as strict JSON. No markdown."},
                {
                    "role": "user",
                    "content": (
                        "Return JSON with keys: supplier_name, invoice_no, invoice_date, items (list of {name, qty, rate, gst_rate, amount}), totals.\n\n"
                        f"INVOICE TEXT:\n{text}"
                    ),
                },
            ],
        )
        out = (resp.choices[0].message.content or "").strip()
        data = json.loads(out)
        items = data.get("items") or []
        totals = data.get("totals") or {}
        return ParsedInvoice(
            supplier_name=str(data.get("supplier_name") or "").strip(),
            invoice_no=str(data.get("invoice_no") or "").strip(),
            invoice_date=str(data.get("invoice_date") or "").strip(),
            items=list(items) if isinstance(items, list) else [],
            totals=totals if isinstance(totals, dict) else {},
            confidence=0.8,
            raw_text=text,
        )
    except Exception:
        logger.exception("LLM invoice parse failed")
        return None
