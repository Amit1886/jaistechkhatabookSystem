from __future__ import annotations

import re
from decimal import Decimal

from django.utils import timezone

from superapp.models import EInvoice, TaxAlert, TaxReport, TaxRule

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def suggest_tax_rate(*, hsn_sac: str = "", product_category: str = "") -> Decimal:
    qs = TaxRule.objects.filter(is_active=True)
    if hsn_sac:
        match = qs.filter(hsn_sac=hsn_sac).order_by("-updated_at").first()
        if match:
            return match.gst_rate
    if product_category:
        match = qs.filter(product_category__iexact=product_category).order_by("-updated_at").first()
        if match:
            return match.gst_rate
    return Decimal("0.00")


def split_gst(taxable_value: Decimal, rate: Decimal, *, seller_state_code: str = "", buyer_state_code: str = ""):
    taxable_value = Decimal(str(taxable_value or "0"))
    rate = Decimal(str(rate or "0"))
    tax = (taxable_value * rate / Decimal("100")).quantize(Decimal("0.01"))
    if seller_state_code and buyer_state_code and seller_state_code != buyer_state_code:
        return {"cgst": Decimal("0.00"), "sgst": Decimal("0.00"), "igst": tax}
    half = (tax / Decimal("2")).quantize(Decimal("0.01"))
    return {"cgst": half, "sgst": tax - half, "igst": Decimal("0.00")}


def validate_gstin(gstin: str) -> bool:
    return bool(gstin and GSTIN_RE.match(gstin.strip().upper()))


def validate_invoice_payload(payload: dict):
    alerts = []
    seller_gstin = (payload.get("seller_gstin") or "").strip().upper()
    buyer_gstin = (payload.get("buyer_gstin") or "").strip().upper()
    invoice_number = (payload.get("invoice_number") or "").strip()
    if seller_gstin and not validate_gstin(seller_gstin):
        alerts.append(("error", "invalid_seller_gstin", "Seller GSTIN format is invalid."))
    if buyer_gstin and not validate_gstin(buyer_gstin):
        alerts.append(("warning", "invalid_buyer_gstin", "Buyer GSTIN format is invalid."))
    if invoice_number and EInvoice.objects.filter(invoice_number=invoice_number, seller_gstin=seller_gstin).exists():
        alerts.append(("warning", "duplicate_invoice", "Duplicate invoice number detected for this seller."))
    created = [
        TaxAlert.objects.create(severity=severity, alert_type=code, message=message, reference=invoice_number, metadata=payload)
        for severity, code, message in alerts
    ]
    return created


def create_einvoice_ready_payload(payload: dict) -> EInvoice:
    taxable_value = Decimal(str(payload.get("taxable_value") or payload.get("subtotal") or "0"))
    rate = Decimal(str(payload.get("gst_rate") or "0"))
    split = split_gst(
        taxable_value,
        rate,
        seller_state_code=str(payload.get("seller_state_code") or ""),
        buyer_state_code=str(payload.get("buyer_state_code") or payload.get("place_of_supply_state_code") or ""),
    )
    invoice = EInvoice.objects.create(
        invoice_number=payload.get("invoice_number") or f"EINV-{timezone.now():%Y%m%d%H%M%S}",
        seller_gstin=(payload.get("seller_gstin") or "").upper(),
        buyer_gstin=(payload.get("buyer_gstin") or "").upper(),
        taxable_value=taxable_value,
        cgst_amount=split["cgst"],
        sgst_amount=split["sgst"],
        igst_amount=split["igst"],
        total_amount=taxable_value + split["cgst"] + split["sgst"] + split["igst"],
        qr_payload=payload,
        status="validated",
        source_type=payload.get("source_type") or "",
        source_id=str(payload.get("source_id") or ""),
        validation_payload={"alerts": [a.alert_type for a in validate_invoice_payload(payload)]},
    )
    return invoice


def build_tax_report(report_type: str, period: str, *, user=None):
    data = {
        "period": period,
        "report_type": report_type,
        "generated_at": timezone.now().isoformat(),
        "summary": {
            "invoice_count": EInvoice.objects.count(),
            "tax_alerts_open": TaxAlert.objects.filter(resolved_at__isnull=True).count(),
        },
    }
    report, _ = TaxReport.objects.update_or_create(
        report_type=report_type,
        period=period,
        defaults={"generated_by": user, "data": data},
    )
    return report

