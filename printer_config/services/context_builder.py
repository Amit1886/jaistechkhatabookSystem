from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils import timezone

from printer_config.models import PrintDocumentType


def _money(value: Any) -> str:
    if value is None:
        return "0.00"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    try:
        return f"{Decimal(str(value)):.2f}"
    except Exception:
        return str(value)


def _safe_name(obj: Any) -> str:
    if obj is None:
        return ""
    if hasattr(obj, "get_full_name"):
        name = obj.get_full_name() or ""
        if name:
            return name
    for field in ("name", "username", "email", "mobile"):
        value = getattr(obj, field, "")
        if value:
            return str(value)
    return str(obj)


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _company_from_user(user) -> dict:
    company = {
        "name": "",
        "address": "",
        "phone": "",
        "email": "",
        "tax_id": "",
        "website": "",
        "logo_url": "",
    }
    if not user:
        return company

    try:
        from accounts.models import UserProfile

        profile = UserProfile.objects.select_related("company").filter(user=user).first()
        if profile:
            company["name"] = profile.business_name or company["name"]
            company["address"] = profile.address or company["address"]
            company["phone"] = profile.mobile or company["phone"]
            company["tax_id"] = profile.gst_number or company["tax_id"]
            if profile.company:
                company["name"] = profile.company.company_name or company["name"]
                company["phone"] = profile.company.mobile or company["phone"]
                company["email"] = profile.company.email or company["email"]
                if getattr(profile.company, "logo", None):
                    company["logo_url"] = profile.company.logo.url
    except Exception:
        pass

    try:
        from core_settings.models import CompanySettings

        global_company = CompanySettings.objects.order_by("id").first()
        if global_company:
            company["name"] = company["name"] or global_company.company_name
            company["phone"] = company["phone"] or global_company.mobile
            company["email"] = company["email"] or global_company.email
            if not company["logo_url"] and getattr(global_company, "logo", None):
                company["logo_url"] = global_company.logo.url
    except Exception:
        pass

    company["name"] = company["name"] or _safe_name(user)
    return company


def _base_context(document_type: str, user=None) -> dict:
    return {
        "company": _company_from_user(user),
        "document": {
            "number": "",
            "type": document_type or PrintDocumentType.INVOICE,
            "date": timezone.localdate().isoformat(),
            "due_date": "",
            "status": "",
        },
        "customer": {
            "name": "",
            "address": "",
            "phone": "",
            "email": "",
            "tax_id": "",
        },
        "seller": {
            "name": _safe_name(user),
            "phone": getattr(user, "mobile", "") if user else "",
            "email": getattr(user, "email", "") if user else "",
        },
        "transport": {
            "vehicle_no": "",
            "driver_name": "",
            "lr_no": "",
            "e_way_bill_no": "",
        },
        "payment": {
            "mode": "",
            "reference": "",
            "status": "",
            "paid_at": "",
        },
        "totals": {
            "subtotal": "0.00",
            "discount": "0.00",
            "tax": "0.00",
            "shipping": "0.00",
            "grand_total": "0.00",
            "paid": "0.00",
            "balance": "0.00",
        },
        "items": [],
        "custom": {},
        "metadata": {},
        "header_text": "",
        "footer_text": "",
        "qr_value": "",
        "barcode_value": "",
        "generated_at": timezone.now().isoformat(),
    }


def _orders_order_context(order) -> dict:
    items = []
    for row in order.items.all():
        name = getattr(row.product, "name", "Item")
        items.append(
            {
                "name": name,
                "sku": getattr(row.product, "sku", ""),
                "barcode": getattr(row.product, "barcode", ""),
                "qty": row.qty,
                "unit": "Nos",
                "price": _money(row.unit_price),
                "discount": _money(row.line_discount),
                "tax": _money(row.tax_percent),
                "amount": _money(row.line_total),
            }
        )

    customer = order.customer
    return {
        "document": {
            "number": order.order_number,
            "type": order.order_type,
            "date": order.created_at.date().isoformat(),
            "status": order.status,
            "due_date": "",
        },
        "customer": {
            "name": _safe_name(customer) or order.walk_in_customer_name,
            "address": "",
            "phone": getattr(customer, "mobile", "") if customer else "",
            "email": getattr(customer, "email", "") if customer else "",
            "tax_id": "",
        },
        "seller": {
            "name": _safe_name(order.salesman),
            "phone": getattr(order.salesman, "mobile", "") if order.salesman else "",
            "email": getattr(order.salesman, "email", "") if order.salesman else "",
        },
        "items": items,
        "totals": {
            "subtotal": _money(order.subtotal),
            "discount": _money(order.discount_amount),
            "tax": _money(order.tax_amount),
            "shipping": "0.00",
            "grand_total": _money(order.total_amount),
            "paid": "0.00",
            "balance": _money(order.total_amount),
        },
        "qr_value": order.order_number,
        "barcode_value": order.order_number,
        "metadata": {
            "source": "orders.order",
            "warehouse": getattr(order.warehouse, "name", ""),
        },
    }


def _commerce_order_context(order) -> dict:
    items = []
    subtotal = Decimal("0.00")
    for row in order.items.all():
        amount = Decimal(row.qty or 0) * Decimal(row.price or 0)
        subtotal += amount
        items.append(
            {
                "name": getattr(row.product, "name", row.raw_name or "Item"),
                "sku": getattr(row.product, "sku", ""),
                "barcode": "",
                "qty": row.qty,
                "unit": getattr(row.product, "unit", "Nos") if row.product else "Nos",
                "price": _money(row.price),
                "discount": "0.00",
                "tax": "0.00",
                "amount": _money(amount),
            }
        )

    grand_total = order.total_amount()
    return {
        "document": {
            "number": f"CO-{order.pk}",
            "type": order.order_type,
            "date": order.created_at.date().isoformat(),
            "status": order.status,
            "due_date": order.payment_due_date.isoformat() if order.payment_due_date else "",
        },
        "customer": {
            "name": getattr(order.party, "name", ""),
            "address": getattr(order.party, "address", ""),
            "phone": getattr(order.party, "mobile", ""),
            "email": getattr(order.party, "email", ""),
            "tax_id": getattr(order.party, "gst", ""),
        },
        "items": items,
        "totals": {
            "subtotal": _money(subtotal),
            "discount": _money(order.discount_amount),
            "tax": _money(order.tax_amount),
            "shipping": "0.00",
            "grand_total": _money(grand_total),
            "paid": _money((grand_total or Decimal("0.00")) - (order.due_amount or Decimal("0.00"))),
            "balance": _money(order.due_amount),
        },
        "qr_value": f"CO-{order.pk}",
        "barcode_value": f"CO-{order.pk}",
        "metadata": {"source": "commerce.order"},
    }


def _commerce_invoice_context(invoice) -> dict:
    order = invoice.order
    payload = _commerce_order_context(order)
    payload["document"]["number"] = invoice.number
    payload["document"]["type"] = PrintDocumentType.INVOICE
    payload["document"]["status"] = invoice.status
    payload["totals"]["grand_total"] = _money(invoice.amount)
    payload["qr_value"] = invoice.number
    payload["barcode_value"] = invoice.number
    payload["payment"]["status"] = invoice.status
    payload["metadata"]["source"] = "commerce.invoice"
    return payload


def _sales_voucher_context(voucher) -> dict:
    items = []
    for row in voucher.items.select_related("product").all():
        amount = Decimal(row.qty or 0) * Decimal(row.rate or 0)
        items.append(
            {
                "name": getattr(row.product, "name", "Item"),
                "sku": getattr(row.product, "sku", ""),
                "barcode": "",
                "qty": row.qty,
                "unit": getattr(row.product, "unit", "Nos"),
                "price": _money(row.rate),
                "discount": "0.00",
                "tax": _money(row.gst_rate),
                "amount": _money(amount),
            }
        )

    number = f"SV-{voucher.invoice_no}"
    return {
        "document": {
            "number": number,
            "type": PrintDocumentType.VOUCHER,
            "date": voucher.date.isoformat(),
            "status": "generated",
            "due_date": "",
        },
        "customer": {
            "name": getattr(voucher.party, "name", ""),
            "address": getattr(voucher.party, "address", ""),
            "phone": getattr(voucher.party, "mobile", ""),
            "email": getattr(voucher.party, "email", ""),
            "tax_id": getattr(voucher.party, "gst", ""),
        },
        "items": items,
        "totals": {
            "subtotal": _money(voucher.total_amount),
            "discount": "0.00",
            "tax": "0.00",
            "shipping": "0.00",
            "grand_total": _money(voucher.total_amount),
            "paid": _money(voucher.total_amount),
            "balance": "0.00",
        },
        "qr_value": number,
        "barcode_value": number,
        "metadata": {"source": "commerce.salesvoucher"},
    }


def _transaction_context(transaction) -> dict:
    number = f"TXN-{transaction.pk}"
    amount = _money(transaction.amount)
    return {
        "document": {
            "number": number,
            "type": PrintDocumentType.RECEIPT,
            "date": transaction.date.isoformat(),
            "status": transaction.txn_type,
            "due_date": "",
        },
        "customer": {
            "name": getattr(transaction.party, "name", ""),
            "address": getattr(transaction.party, "address", ""),
            "phone": getattr(transaction.party, "mobile", ""),
            "email": getattr(transaction.party, "email", ""),
            "tax_id": getattr(transaction.party, "gst", ""),
        },
        "items": [
            {
                "name": "Transaction Entry",
                "sku": "",
                "barcode": "",
                "qty": 1,
                "unit": "Nos",
                "price": amount,
                "discount": "0.00",
                "tax": "0.00",
                "amount": amount,
            }
        ],
        "payment": {
            "mode": transaction.txn_mode,
            "reference": "",
            "status": transaction.txn_type,
            "paid_at": transaction.date.isoformat(),
        },
        "totals": {
            "subtotal": amount,
            "discount": "0.00",
            "tax": "0.00",
            "shipping": "0.00",
            "grand_total": amount,
            "paid": amount,
            "balance": "0.00",
        },
        "qr_value": number,
        "barcode_value": number,
        "metadata": {"source": "khataapp.transaction"},
    }


def _payment_tx_context(payment_tx) -> dict:
    ref = payment_tx.external_ref or f"PAY-{payment_tx.pk}"
    return {
        "document": {
            "number": ref,
            "type": PrintDocumentType.PAYMENT_RECEIPT,
            "date": payment_tx.created_at.date().isoformat(),
            "status": payment_tx.status,
            "due_date": "",
        },
        "customer": {
            "name": _safe_name(payment_tx.user),
            "address": "",
            "phone": getattr(payment_tx.user, "mobile", "") if payment_tx.user else "",
            "email": getattr(payment_tx.user, "email", "") if payment_tx.user else "",
            "tax_id": "",
        },
        "payment": {
            "mode": payment_tx.mode,
            "reference": payment_tx.external_ref,
            "status": payment_tx.status,
            "paid_at": payment_tx.created_at.isoformat(),
        },
        "totals": {
            "subtotal": _money(payment_tx.amount),
            "discount": "0.00",
            "tax": "0.00",
            "shipping": "0.00",
            "grand_total": _money(payment_tx.amount),
            "paid": _money(payment_tx.amount),
            "balance": "0.00",
        },
        "qr_value": ref,
        "barcode_value": ref,
        "metadata": {"source": "payments.paymenttransaction"},
    }


def _source_context(source_model: str, source_id: Any) -> dict:
    source = (source_model or "").strip().lower()
    if not source or source_id in (None, ""):
        return {}

    try:
        if source in {"orders.order", "order"}:
            from orders.models import Order

            obj = Order.objects.select_related("customer", "salesman", "warehouse").prefetch_related("items__product").get(
                pk=source_id
            )
            return _orders_order_context(obj)

        if source in {"commerce.order"}:
            from commerce.models import Order

            obj = Order.objects.select_related("party").prefetch_related("items__product").get(pk=source_id)
            return _commerce_order_context(obj)

        if source in {"commerce.invoice", "invoice"}:
            from commerce.models import Invoice

            obj = Invoice.objects.select_related("order__party").get(pk=source_id)
            return _commerce_invoice_context(obj)

        if source in {"commerce.salesvoucher", "voucher"}:
            from commerce.models import SalesVoucher

            obj = SalesVoucher.objects.select_related("party").prefetch_related("items__product").get(pk=source_id)
            return _sales_voucher_context(obj)

        if source in {"khataapp.transaction", "transaction"}:
            from khataapp.models import Transaction

            obj = Transaction.objects.select_related("party").get(pk=source_id)
            return _transaction_context(obj)

        if source in {"payments.paymenttransaction", "payment"}:
            from payments.models import PaymentTransaction

            obj = PaymentTransaction.objects.select_related("user", "order").get(pk=source_id)
            return _payment_tx_context(obj)
    except Exception:
        return {}
    return {}


def build_document_context(
    document_type: str,
    source_model: str = "",
    source_id: Any = None,
    payload: dict | None = None,
    user=None,
) -> dict:
    """
    Build dynamic context for any print document type.
    """
    data = _base_context(document_type=document_type, user=user)
    from_source = _source_context(source_model=source_model, source_id=source_id)
    _deep_merge(data, from_source)
    _deep_merge(data, payload or {})
    return data


def build_dummy_context(document_type: str, user=None):
    payload = {
        "document": {
            "number": "DEMO-2026-0012",
            "type": document_type,
            "date": timezone.localdate().isoformat(),
            "status": "paid",
            "due_date": "",
        },
        "customer": {
            "name": "Demo Customer",
            "address": "Demo Street, City",
            "phone": "9000000000",
            "email": "customer@example.com",
            "tax_id": "22ABCDE1234F1Z5",
        },
        "items": [
            {
                "name": "Sample Product A",
                "sku": "SKU-001",
                "barcode": "8901234567890",
                "qty": 2,
                "unit": "Nos",
                "price": "120.00",
                "discount": "10.00",
                "tax": "18.00",
                "amount": "230.00",
            },
            {
                "name": "Sample Product B",
                "sku": "SKU-002",
                "barcode": "8901234567891",
                "qty": 1,
                "unit": "Nos",
                "price": "80.00",
                "discount": "0.00",
                "tax": "14.40",
                "amount": "94.40",
            },
        ],
        "totals": {
            "subtotal": "320.00",
            "discount": "10.00",
            "tax": "32.40",
            "shipping": "0.00",
            "grand_total": "342.40",
            "paid": "200.00",
            "balance": "142.40",
        },
        "payment": {"mode": "upi", "reference": "UPI-REF-001", "status": "success", "paid_at": timezone.now().isoformat()},
        "transport": {"vehicle_no": "UP32AB1234", "driver_name": "Ram Kumar", "lr_no": "LR-22019", "e_way_bill_no": "EWB123456789"},
        "header_text": "Thank you for doing business with us.",
        "footer_text": "This is a system generated print.",
        "qr_value": "DEMO-2026-0012",
        "barcode_value": "DEMO-2026-0012",
        "custom": {
            "whatsapp_number": "+91 90000 00000",
            "map_query": "Shop 14, Civil Lines, Lucknow",
            "social_links": {
                "instagram": "https://instagram.com/jaistech",
                "facebook": "https://facebook.com/jaistech",
            },
            "bank_details": {
                "account_name": "Demotest3 Retail Pvt Ltd",
                "account_no": "123456789012",
                "ifsc": "SBIN0000123",
                "upi_id": "demotest3@upi",
            },
            "terms_conditions": "Goods once sold will not be taken back. Subject to Lucknow jurisdiction.",
        },
    }
    return build_document_context(document_type=document_type, source_model="", source_id=None, payload=payload, user=user)
