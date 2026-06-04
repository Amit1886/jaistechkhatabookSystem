from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from commerce.models import Invoice


@dataclass(frozen=True)
class GstMismatch:
    ok: bool
    message: str = ""


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def check_gst_mismatch(invoice: Invoice) -> GstMismatch:
    """
    Simple checks:
    - gst_type == GST but order.tax_percent is 0
    - gst_type != GST but order.tax_percent > 0
    """
    if not invoice:
        return GstMismatch(ok=True)
    gst_type = (getattr(invoice, "gst_type", "") or "").upper()
    order = getattr(invoice, "order", None)
    tax_percent = _to_decimal(getattr(order, "tax_percent", None))

    if gst_type == "GST" and tax_percent <= 0:
        return GstMismatch(ok=False, message="Invoice marked GST but tax percent is 0.")
    if gst_type != "GST" and tax_percent > 0:
        return GstMismatch(ok=False, message="Invoice marked NON-GST but tax percent is > 0.")
    return GstMismatch(ok=True)

