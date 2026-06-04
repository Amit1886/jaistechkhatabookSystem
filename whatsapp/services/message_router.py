from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from django.core.cache import cache
from django.db.models import Count, Sum
from django.utils import timezone

from commerce.models import Invoice, Payment, Product
from smart_bi.models import BusinessMetric
from whatsapp.models import BroadcastCampaign, Customer, WhatsAppAccount, WhatsAppOperator
from whatsapp.parser import parse_accounting_command

logger = logging.getLogger(__name__)

_WS = re.compile(r"\s+")
_DIGITS = re.compile(r"[^0-9]")


@dataclass(frozen=True)
class EngineResult:
    ok: bool
    reply: str
    intent: str = ""
    reference_type: str = ""
    reference_id: Optional[int] = None
    order_id: Optional[int] = None
    invoice_id: Optional[int] = None
    payment_url: str = ""
    invoice_pdf_url: str = ""
    attachments: tuple[dict[str, Any], ...] = ()


def _digits(value: str) -> str:
    return _DIGITS.sub("", value or "").strip()


def _last10(value: str) -> str:
    d = _digits(value)
    return d[-10:] if len(d) > 10 else d


def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "").strip()).strip()


def _ai_enabled() -> bool:
    flag = (os.getenv("WHATSAPP_AI_ENABLED") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _ai_model() -> str:
    return (os.getenv("WHATSAPP_AI_MODEL") or "").strip() or "gpt-4o-mini"


def _openai_client():
    try:
        from openai import OpenAI  # type: ignore

        return OpenAI()
    except Exception:
        return None


def _classify_intent_ai(*, message: str, history: str) -> str:
    """
    Optional intent classification (Hindi+English).

    Returns one of the fixed intent strings, or "" when unavailable.
    """
    if not _ai_enabled():
        return ""
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return ""
    client = _openai_client()
    if not client:
        return ""

    text = _norm(message)
    if not text:
        return ""

    intents = [
        "customer_support",
        "new_lead",
        "product_inquiry",
        "place_order",
        "cart_management",
        "invoice_request",
        "payment_query",
        "supplier_order",
        "supplier_payment",
        "marketing_response",
        "report_request",
        "inventory_query",
        "unknown",
    ]

    try:
        resp = client.chat.completions.create(
            model=_ai_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the WhatsApp message into ONE intent from this list:\n"
                        + ", ".join(intents)
                        + "\nReturn ONLY the intent string."
                    ),
                },
                {"role": "user", "content": f"Message:\n{text}\n\nRecent chat:\n{history or '(none)'}"},
            ],
            temperature=0.0,
        )
        out = ""
        try:
            out = (resp.choices[0].message.content or "").strip()
        except Exception:
            out = ""
        out = out.splitlines()[0].strip() if out else ""
        return out if out in intents else ""
    except Exception:
        return ""


def _operator_numbers_last10(*, owner, account: WhatsAppAccount) -> set[str]:
    """
    Cached set of last-10 digits for operator/admin numbers for this WhatsAppAccount.
    """
    key = f"wa:ops:{account.id}"
    cached = cache.get(key)
    if isinstance(cached, list):
        return set(str(x) for x in cached if x)

    numbers: set[str] = set()
    try:
        if getattr(owner, "mobile", None):
            numbers.add(_last10(str(getattr(owner, "mobile") or "")))
    except Exception:
        pass

    try:
        qs = (
            WhatsAppOperator.objects.filter(owner=owner, whatsapp_account=account, is_active=True)
            .values_list("phone_number", flat=True)[:500]
        )
        for n in qs:
            d10 = _last10(str(n or ""))
            if d10:
                numbers.add(d10)
    except Exception:
        logger.exception("Failed to load WhatsAppOperator list")

    cache.set(key, list(numbers), timeout=5 * 60)
    return numbers


def _is_operator(*, owner, account: WhatsAppAccount, from_number: str) -> bool:
    d10 = _last10(from_number)
    if not d10:
        return False
    return d10 in _operator_numbers_last10(owner=owner, account=account)


def _operator_help_text() -> str:
    return (
        "Admin WhatsApp Commands:\n"
        "- sales today\n"
        "- payments today\n"
        "- low stock\n"
        "- stock <product>\n"
        "- health\n"
        "- reorder\n"
        "- supplier dues\n"
        "- broadcast all: <message>\n"
        "- broadcast tag <tag>: <message>\n\n"
        "Accounting:\n"
        "- sale 5 item 250\n"
        "- expense diesel 500\n"
        "- receive payment 5000 from Party\n"
        "- pay 1200 to Supplier"
    )


def _report_sales_today(*, owner, day: date) -> str:
    qs = Invoice.objects.filter(order__owner=owner, created_at__date=day)
    agg = qs.aggregate(total=Sum("amount"), count=Count("id"))
    total = agg.get("total") or 0
    count = agg.get("count") or 0
    return f"Sales {day.strftime('%d %b')}: {count} invoices, Total Rs. {total}"


def _report_payments_today(*, owner, day: date) -> str:
    qs = Payment.objects.filter(invoice__order__owner=owner, is_deleted=False, created_at__date=day)
    agg = qs.aggregate(total=Sum("amount"), count=Count("id"))
    total = agg.get("total") or 0
    count = agg.get("count") or 0
    return f"Collections {day.strftime('%d %b')}: {count} payments, Total Rs. {total}"


def _report_low_stock(*, owner) -> str:
    qs = Product.objects.filter(owner=owner).only("id", "name", "stock", "min_stock").order_by("stock", "name")
    low = [p for p in qs[:400] if (p.stock is not None and p.min_stock is not None and p.stock <= p.min_stock)]
    if not low:
        return "Low stock: none."
    lines = [f"- {p.name}: {p.stock} (min {p.min_stock})" for p in low[:25]]
    more = "\n..." if len(low) > 25 else ""
    return "Low stock items:\n" + "\n".join(lines) + more


def _report_business_health(*, owner) -> str:
    m = BusinessMetric.objects.filter(owner=owner).order_by("-date", "-id").first()
    if not m:
        return "Business Health: not available yet. Open dashboard once to generate metrics."
    return (
        f"Business Health ({m.date}): {int(m.health_score or 0)}/100\n"
        f"Sales: ₹{m.total_sales} | Profit: ₹{m.total_profit}\n"
        f"Expense: ₹{m.total_expense} | Outstanding: ₹{m.outstanding_due}\n"
        f"Stock Value: ₹{m.stock_value}"
    )


def _report_reorder(*, owner) -> str:
    try:
        from ai_insights.stock_analyzer import compute_reorder_suggestions

        items = compute_reorder_suggestions(owner, days=30, limit=10)
    except Exception:
        items = []
    if not items:
        return "Reorder suggestions: none (need more sales history)."
    lines = [f"- {it['name']}: stock {it['stock']} (≈{it['days_left']} days left) → buy {it['suggest_reorder_qty']}" for it in items]
    return "Reorder suggestions (30 days):\n" + "\n".join(lines)


def _report_supplier_dues(*, owner) -> str:
    from commerce.models import Order

    today = timezone.localdate()
    qs = (
        Order.objects.filter(owner=owner, order_type="PURCHASE")
        .exclude(status__in=["cancelled", "rejected"])
        .filter(due_amount__gt=0)
        .order_by("payment_due_date", "-created_at")[:20]
    )
    if not qs:
        return "Supplier dues: none."

    lines = []
    overdue = 0
    for o in qs:
        due = getattr(o, "due_amount", None)
        if due is None:
            continue
        dd = getattr(o, "payment_due_date", None)
        if dd and dd < today:
            overdue += 1
        party = getattr(o, "party", None)
        party_name = getattr(party, "name", "") if party else "Supplier"
        inv = (getattr(o, "invoice_number", "") or "").strip()
        inv_txt = f" inv {inv}" if inv else ""
        dd_txt = f" due {dd}" if dd else ""
        lines.append(f"- {party_name}: ₹{due}{inv_txt}{dd_txt}")

    head = f"Supplier dues ({overdue} overdue):"
    return head + "\n" + "\n".join(lines)


def _product_stock(*, owner, query: str) -> str:
    query = (query or "").strip()
    if not query:
        return "Usage: stock <product name>"
    p = Product.objects.filter(owner=owner, name__icontains=query).order_by("name").first()
    if not p:
        p = Product.objects.filter(name__icontains=query).order_by("name").first()
    if not p:
        return "Product not found."
    return f"{p.name} stock: {p.stock} (min {p.min_stock}) price Rs. {p.price}"


def _enqueue_broadcast(*, campaign: BroadcastCampaign) -> None:
    # Import locally to avoid circular imports with whatsapp.tasks (tasks imports router).
    from khatapro import DISABLE_CELERY
    from whatsapp.tasks import run_broadcast_campaign

    if DISABLE_CELERY:
        try:
            run_broadcast_campaign.run(str(campaign.id))  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Broadcast run failed (sync)")
        return
    try:
        run_broadcast_campaign.apply_async(args=(str(campaign.id),), retry=False, ignore_result=True)
    except Exception:
        try:
            run_broadcast_campaign.run(str(campaign.id))  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Broadcast run failed (fallback sync)")


def _operator_broadcast(*, owner, account: WhatsAppAccount, text: str) -> EngineResult:
    """
    Commands:
    - broadcast all: hello
    - broadcast tag vip: hello
    """
    m = re.match(r"^\s*broadcast\s+(?P<mode>all|tag)\s*(?P<tag>\w+)?\s*[:\-]?\s*(?P<body>.+)\s*$", text, flags=re.IGNORECASE)
    if not m:
        return EngineResult(ok=False, reply="Usage: broadcast all: <message> OR broadcast tag <tag>: <message>", intent="broadcast")

    mode = (m.group("mode") or "").strip().lower()
    tag = (m.group("tag") or "").strip().lower()
    body = (m.group("body") or "").strip()
    if not body:
        return EngineResult(ok=False, reply="Broadcast message is empty.", intent="broadcast")

    target_type = BroadcastCampaign.TargetType.ALL_CUSTOMERS
    target_payload: dict[str, Any] = {}
    if mode == "tag":
        if not tag:
            return EngineResult(ok=False, reply="Usage: broadcast tag <tag>: <message>", intent="broadcast")
        target_type = BroadcastCampaign.TargetType.CUSTOMER_TAG
        target_payload = {"tag": tag}

    name = f"WA Broadcast {timezone.now().strftime('%d %b %H:%M')}"
    camp = BroadcastCampaign.objects.create(
        owner=owner,
        whatsapp_account=account,
        name=name,
        status=BroadcastCampaign.Status.DRAFT,
        target_type=target_type,
        target_payload=target_payload,
        message_type=BroadcastCampaign.MessageType.TEXT,
        text=body,
    )
    _enqueue_broadcast(campaign=camp)
    return EngineResult(ok=True, reply=f"Broadcast started: {camp.name}", intent="broadcast", reference_type="whatsapp.BroadcastCampaign", reference_id=None)


def _operator_handle(*, owner, account: WhatsAppAccount, customer: Customer, inbound_text: str) -> Optional[EngineResult]:
    text = _norm(inbound_text)
    if not text:
        return None

    low = text.lower()

    if low in {"help", "menu", "admin help", "admin", "commands", "cmd"}:
        return EngineResult(ok=True, reply=_operator_help_text(), intent="admin_help")

    if low.startswith("broadcast"):
        return _operator_broadcast(owner=owner, account=account, text=text)

    today = timezone.localdate()
    if "sales" in low and "today" in low:
        return EngineResult(ok=True, reply=_report_sales_today(owner=owner, day=today), intent="report_sales_today")
    if ("payment" in low or "collection" in low) and "today" in low:
        return EngineResult(ok=True, reply=_report_payments_today(owner=owner, day=today), intent="report_payments_today")
    if "low stock" in low or "stock low" in low:
        return EngineResult(ok=True, reply=_report_low_stock(owner=owner), intent="report_low_stock")
    if low.startswith("stock "):
        q = text.split(" ", 1)[1].strip() if " " in text else ""
        return EngineResult(ok=True, reply=_product_stock(owner=owner, query=q), intent="inventory_query")
    if low in {"health", "business health", "health score"}:
        return EngineResult(ok=True, reply=_report_business_health(owner=owner), intent="report_business_health")
    if low in {"reorder", "reorder list", "purchase predict", "purchase prediction", "buy list"}:
        return EngineResult(ok=True, reply=_report_reorder(owner=owner), intent="report_reorder")
    if low in {"supplier dues", "supplier due", "purchase dues", "dues suppliers"}:
        return EngineResult(ok=True, reply=_report_supplier_dues(owner=owner), intent="report_supplier_dues")

    # Accounting commands (sale/expense/payments)
    parsed = parse_accounting_command(text)
    if parsed:
        try:
            from whatsapp.message_handler import execute_parsed_command

            res = execute_parsed_command(owner=owner, parsed=parsed)
            return EngineResult(
                ok=res.ok,
                reply=res.reply,
                intent=res.intent or "accounting",
                reference_type=res.reference_type or "",
                reference_id=res.reference_id,
            )
        except Exception:
            logger.exception("Operator accounting command failed")
            return EngineResult(ok=False, reply="Failed to process. Type 'help' for commands.", intent="accounting_error")

    # Optional AI intent hint (does not execute actions by itself yet).
    try:
        history = ""
        # Keep history small for safety; operator messages are rare.
        intent = _classify_intent_ai(message=text, history=history)
        if intent in {"report_request", "inventory_query"}:
            return EngineResult(ok=True, reply="Type: sales today / payments today / low stock / stock <product>", intent="admin_hint")
    except Exception:
        pass

    return None


def route_inbound_message(*, owner, account: WhatsAppAccount, customer: Customer, inbound_text: str) -> EngineResult:
    """
    Central WhatsApp message router.

    - Detects operator/admin messages (reports, accounting, broadcasts)
    - Falls back to existing bot engine (flows + commerce + AI smart replies)
    """
    try:
        if _is_operator(owner=owner, account=account, from_number=customer.phone_number or ""):
            op = _operator_handle(owner=owner, account=account, customer=customer, inbound_text=inbound_text)
            if op and (op.reply or op.attachments or op.invoice_pdf_url):
                return op
    except Exception:
        logger.exception("Operator routing failed")

    # Default: existing bot engine (customer/supplier messages)
    from whatsapp.services.bot_engine import generate_reply

    res = generate_reply(owner=owner, account=account, customer=customer, inbound_text=inbound_text)
    return EngineResult(
        ok=res.ok,
        reply=res.reply,
        intent=res.intent,
        reference_type=res.reference_type,
        reference_id=res.reference_id,
        order_id=res.order_id,
        invoice_id=res.invoice_id,
        payment_url=res.payment_url,
        invoice_pdf_url=res.invoice_pdf_url,
        attachments=res.attachments,
    )
