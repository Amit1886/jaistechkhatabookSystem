from __future__ import annotations

from decimal import Decimal

from accounts.utils import render_to_pdf_bytes


def render_store_order_invoice_pdf_bytes(*, order, request=None):
    items = order.items.select_related("product").all().order_by("id")
    subtotal = order.subtotal_amount or Decimal("0.00")
    tax = order.tax_amount or Decimal("0.00")
    total = order.total_amount or Decimal("0.00")

    # Basic GST split (CGST/SGST) for India-first default. Extend per vendor settings if needed.
    is_gst = tax > 0
    cgst = sgst = Decimal("0.00")
    if is_gst:
        cgst = (tax / Decimal("2")).quantize(Decimal("0.01"))
        sgst = tax - cgst

    context = {
        "order": order,
        "vendor": order.vendor,
        "customer": order.customer,
        "address": order.address,
        "items": items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "is_gst": is_gst,
        "cgst": cgst,
        "sgst": sgst,
    }
    return render_to_pdf_bytes("storefront/invoice_print.html", context, request=request)

