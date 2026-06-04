from __future__ import annotations

import logging
import os
import uuid
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from ai_ocr.forms import InvoiceImageUploadForm
from ai_ocr.invoice_reader import read_invoice_from_upload
from ai_ocr.models import OCRInvoiceLog
from commerce.models import Invoice, Order, OrderItem, Product
from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry
from khataapp.models import Party

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return Decimal("0.00")


def _get_global_setting(key: str, default: Any = "") -> Any:
    try:
        sync_settings_registry()
    except Exception:
        pass
    try:
        definition = SettingDefinition.objects.filter(key=key).first()
        if not definition:
            return default
        value_obj = SettingValue.objects.filter(definition=definition, owner__isnull=True).first()
        return value_obj.value if value_obj else definition.default_value
    except Exception:
        return default


def _match_or_create_product(owner, name: str, unit_price: Decimal) -> Product:
    name = (name or "").strip() or "OCR Item"
    p = Product.objects.filter(owner=owner, name__iexact=name).first()
    if p:
        return p
    sku = f"OCR-{uuid.uuid4().hex[:10].upper()}"
    return Product.objects.create(
        owner=owner,
        name=name[:100],
        price=unit_price if unit_price > 0 else Decimal("0.00"),
        stock=0,
        min_stock=0,
        sku=sku,
        unit="pcs",
    )


def _get_or_create_supplier(owner, supplier_name: str) -> Party:
    supplier_name = (supplier_name or "").strip() or "OCR Supplier"
    party = Party.objects.filter(owner=owner, party_type="supplier", name__iexact=supplier_name).first()
    if party:
        return party
    return Party.objects.create(owner=owner, party_type="supplier", name=supplier_name[:100])


def _best_gst_rate(parsed_data: dict[str, Any]) -> Decimal:
    totals = parsed_data.get("totals") or {}
    if isinstance(totals, dict):
        gst = _to_decimal(totals.get("gst_rate") or 0)
        if gst > 0:
            return gst.quantize(Decimal("0.01"))

    items = parsed_data.get("items") or []
    best = Decimal("0.00")
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            gst = _to_decimal(it.get("gst_rate") or it.get("tax_percent") or 0)
            if gst > best:
                best = gst
    if best < 0 or best > 100:
        return Decimal("0.00")
    return best.quantize(Decimal("0.01"))


@login_required
def ocr_invoice_dashboard(request):
    if not bool(_get_global_setting("ai_tools_enabled", True)) or not bool(_get_global_setting("ocr_enabled", True)):
        messages.error(request, "OCR Invoice Entry is disabled by admin settings.")
        return redirect("accounts:dashboard")

    upload_form = InvoiceImageUploadForm(request.POST or None, request.FILES or None)
    parsed_preview = None
    log_id = None

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "upload" and upload_form.is_valid():
            img = upload_form.cleaned_data["image"]
            log = OCRInvoiceLog.objects.create(owner=request.user, image=img, status=OCRInvoiceLog.Status.UPLOADED)
            try:
                result = read_invoice_from_upload(img)
                if not result.ok or not result.parsed:
                    log.status = OCRInvoiceLog.Status.FAILED
                    log.error = result.ocr.error or "OCR failed"
                    log.save(update_fields=["status", "error"])
                    err = (log.error or "OCR failed").strip()
                    messages.error(request, f"OCR failed: {err[:200]}")
                    return redirect(request.path)

                parsed = result.parsed
                parsed_dict = {
                    "supplier_name": parsed.supplier_name,
                    "invoice_no": parsed.invoice_no,
                    "invoice_date": parsed.invoice_date,
                    "items": parsed.items,
                    "totals": parsed.totals,
                    "confidence": parsed.confidence,
                }
                log.extracted_text = result.ocr.text
                log.parsed_data = parsed_dict
                log.status = OCRInvoiceLog.Status.PARSED
                log.save(update_fields=["extracted_text", "parsed_data", "status"])
                parsed_preview = parsed_dict
                log_id = log.id
                messages.success(request, "Invoice extracted. Review and confirm creation.")
            except Exception as e:
                logger.exception("OCR invoice read failed")
                log.status = OCRInvoiceLog.Status.FAILED
                log.error = f"{type(e).__name__}: {e}"
                log.save(update_fields=["status", "error"])
                messages.error(request, f"OCR processing failed: {log.error[:200]}")
                return redirect(request.path)

        if action == "create_purchase":
            log_id_raw = (request.POST.get("log_id") or "").strip()
            log = get_object_or_404(OCRInvoiceLog, id=log_id_raw, owner=request.user)
            if log.status not in {OCRInvoiceLog.Status.PARSED, OCRInvoiceLog.Status.OCR_OK}:
                messages.error(request, "This OCR log is not ready to create a purchase.")
                return redirect(request.path)

            data = log.parsed_data or {}
            supplier = _get_or_create_supplier(request.user, str(data.get("supplier_name") or ""))
            inv_no = str(data.get("invoice_no") or "").strip()
            gst_rate = _best_gst_rate(data if isinstance(data, dict) else {})

            items = data.get("items") or []
            if not isinstance(items, list) or not items:
                messages.error(request, "No items detected to create a purchase entry.")
                return redirect(request.path)

            with transaction.atomic():
                order = Order.objects.create(
                    owner=request.user,
                    party=supplier,
                    order_type="PURCHASE",
                    status="completed",
                    invoice_number=inv_no or None,
                    notes="Created from OCR Invoice Entry",
                    order_source="OCR",
                    tax_percent=gst_rate if gst_rate > 0 else Decimal("0.00"),
                )
                for it in items:
                    try:
                        name = str(it.get("name") or it.get("product") or "").strip()
                        qty = int(_to_decimal(it.get("qty") or 1))
                        qty = max(qty, 1)
                        amount = _to_decimal(it.get("amount") or 0)
                        rate = _to_decimal(it.get("rate") or 0)
                        item_tax = _to_decimal(it.get("gst_rate") or it.get("tax_percent") or gst_rate or 0)
                        if rate <= 0 and amount > 0:
                            rate = (amount / Decimal(qty)).quantize(Decimal("0.01"))
                        prod = _match_or_create_product(request.user, name, rate)
                        OrderItem.objects.create(
                            order=order,
                            product=prod,
                            qty=qty,
                            price=rate,
                            tax_percent=item_tax if item_tax > 0 else Decimal("0.00"),
                        )
                    except Exception:
                        continue

                # Recompute totals after items are created so invoice amounts stay consistent.
                order.save()

                inv = Invoice.objects.create(order=order, gst_type=("GST" if gst_rate > 0 else "NON_GST"))
                log.reference_type = "commerce.Order"
                log.reference_id = order.id
                log.status = OCRInvoiceLog.Status.CREATED
                log.save(update_fields=["reference_type", "reference_id", "status"])

            messages.success(request, f"Purchase entry created: Order #{order.id}")
            return redirect(reverse("commerce:order_detail", kwargs={"pk": order.id}))

    recent_logs = OCRInvoiceLog.objects.filter(owner=request.user).order_by("-created_at")[:20]
    openai_key_set = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    ocr_model = str(_get_global_setting("ocr_model", "") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    return render(
        request,
        "ai_ocr/dashboard.html",
        {
            "upload_form": upload_form,
            "parsed_preview": parsed_preview,
            "log_id": log_id,
            "recent_logs": recent_logs,
            "openai_key_set": openai_key_set,
            "ocr_model": ocr_model,
        },
    )
