import json
import logging
import re
from datetime import date as date_type
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone

from .models import SMSLog, SMSTemplate
from .sms_service import send_google_sms

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"{{\s*(\w+)\s*}}")


def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, date_type) and not hasattr(value, "hour"):
        return value.strftime("%Y-%m-%d")
    try:
        return timezone.localtime(value).strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def _format_amount(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{Decimal(str(value)):.2f}"
    except Exception:
        return str(value)


def render_sms_template(text: str, context: Dict[str, Any]) -> str:
    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        val = context.get(key)
        return "" if val is None else str(val)

    return _VAR_PATTERN.sub(_replace, text or "")


def _get_company_auto_sms_enabled() -> bool:
    try:
        from khataapp.models import CompanySettings

        cs = CompanySettings.objects.first()
        if cs is None:
            return True
        return bool(getattr(cs, "auto_sms_send", True))
    except Exception:
        return True


def _get_enabled_template(template_type: str) -> Optional[SMSTemplate]:
    return (
        SMSTemplate.objects.filter(template_type=template_type, enabled=True).order_by("-id").first()
    )


def _send_for_template(template_type: str, mobile: str, context: Dict[str, Any]) -> None:
    template = _get_enabled_template(template_type)
    if not template:
        SMSLog.objects.create(
            mobile=mobile or "",
            message="",
            template=None,
            status=SMSLog.Status.SKIPPED,
            response=f"No enabled template for type '{template_type}'.",
        )
        return

    message = render_sms_template(
        template.message_text,
        {
            "name": context.get("name", ""),
            "amount": _format_amount(context.get("amount")),
            "invoice_no": context.get("invoice_no", ""),
            "date": _format_date(context.get("date")),
        },
    )

    if not _get_company_auto_sms_enabled():
        SMSLog.objects.create(
            mobile=mobile or "",
            message=message,
            template=template,
            status=SMSLog.Status.SKIPPED,
            response="Auto SMS sending is disabled in CompanySettings.",
        )
        return

    result = send_google_sms(mobile=mobile, text_message=message, image_url=template.image_url or None)
    ok = bool(result.get("ok"))
    SMSLog.objects.create(
        mobile=mobile or "",
        message=message,
        template=template,
        status=SMSLog.Status.SENT if ok else SMSLog.Status.FAILED,
        response=json.dumps(result, ensure_ascii=False, default=str),
    )


def _safe_mobile(value: Optional[str]) -> str:
    value = (value or "").strip()
    return value


def _handle_order(instance: Any) -> None:
    party = getattr(instance, "party", None)
    mobile = _safe_mobile(getattr(party, "sms_number", "") or getattr(party, "mobile", ""))
    if not mobile:
        SMSLog.objects.create(
            mobile="",
            message="",
            template=None,
            status=SMSLog.Status.SKIPPED,
            response="Order has no party mobile/sms_number.",
        )
        return

    context = {
        "name": getattr(party, "name", "") if party else "",
        "amount": None,
        "invoice_no": getattr(instance, "invoice_number", "") or str(getattr(instance, "pk", "")),
        "date": getattr(instance, "created_at", None) or getattr(instance, "order_date", None),
    }
    try:
        # commerce.Order has total_amount() method
        if callable(getattr(instance, "total_amount", None)):
            context["amount"] = instance.total_amount()
    except Exception:
        pass
    _send_for_template(SMSTemplate.TemplateType.ORDER, mobile, context)


def _handle_invoice(instance: Any) -> None:
    order = getattr(instance, "order", None)
    party = getattr(order, "party", None) if order else None
    mobile = _safe_mobile(getattr(party, "sms_number", "") or getattr(party, "mobile", ""))
    if not mobile:
        SMSLog.objects.create(
            mobile="",
            message="",
            template=None,
            status=SMSLog.Status.SKIPPED,
            response="Invoice has no party mobile/sms_number.",
        )
        return

    context = {
        "name": getattr(party, "name", "") if party else "",
        "amount": getattr(instance, "amount", None),
        "invoice_no": getattr(instance, "number", "") or str(getattr(instance, "pk", "")),
        "date": getattr(instance, "created_at", None),
    }
    _send_for_template(SMSTemplate.TemplateType.INVOICE, mobile, context)


def _handle_voucher(instance: Any) -> None:
    party = getattr(instance, "party", None)
    mobile = _safe_mobile(getattr(party, "sms_number", "") or getattr(party, "mobile", ""))
    if not mobile:
        SMSLog.objects.create(
            mobile="",
            message="",
            template=None,
            status=SMSLog.Status.SKIPPED,
            response="Voucher has no party mobile/sms_number.",
        )
        return

    context = {
        "name": getattr(party, "name", "") if party else "",
        "amount": getattr(instance, "total_amount", None),
        "invoice_no": str(getattr(instance, "invoice_no", "") or getattr(instance, "pk", "")),
        "date": getattr(instance, "date", None),
    }
    _send_for_template(SMSTemplate.TemplateType.VOUCHER, mobile, context)


def _handle_billing(instance: Any) -> None:
    user = getattr(instance, "user", None)
    mobile = _safe_mobile(getattr(user, "mobile", ""))
    if not mobile:
        SMSLog.objects.create(
            mobile="",
            message="",
            template=None,
            status=SMSLog.Status.SKIPPED,
            response="Billing invoice has no user mobile.",
        )
        return

    context = {
        "name": getattr(user, "username", "") or getattr(user, "email", "") if user else "",
        "amount": getattr(instance, "amount", None),
        "invoice_no": getattr(instance, "invoice_number", "") or str(getattr(instance, "pk", "")),
        "date": getattr(instance, "created_at", None),
    }
    _send_for_template(SMSTemplate.TemplateType.BILLING, mobile, context)


def _connect() -> None:
    try:
        from commerce.models import Invoice as CommerceInvoice
        from commerce.models import Order as CommerceOrder
        from commerce.models import SalesVoucher
        from billing.models import BillingInvoice
    except Exception:
        logger.exception("sms_center: failed to import senders for signal registration")
        return

    def _on_created(handler):
        def _wrapper(sender, instance, created, **kwargs):
            if not created:
                return
            transaction.on_commit(lambda: handler(instance))

        return _wrapper

    post_save.connect(_on_created(_handle_order), sender=CommerceOrder, dispatch_uid="sms_center_order_create")
    post_save.connect(_on_created(_handle_invoice), sender=CommerceInvoice, dispatch_uid="sms_center_invoice_create")
    post_save.connect(_on_created(_handle_voucher), sender=SalesVoucher, dispatch_uid="sms_center_voucher_create")
    post_save.connect(_on_created(_handle_billing), sender=BillingInvoice, dispatch_uid="sms_center_billing_create")


_connect()
