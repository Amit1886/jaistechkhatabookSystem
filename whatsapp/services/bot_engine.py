from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from django.db import transaction

from commerce.services.whatsapp_conversation import ConversationResult, handle_whatsapp_order_message
from khataapp.models import Party
from whatsapp.models import Bot, BotFlow, BotMessage, Customer, WhatsAppAccount
from whatsapp.services.smart_reply import smart_reply

logger = logging.getLogger(__name__)


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


def _norm(text: str) -> str:
    return (text or "").strip()


def _match_flow(flow: BotFlow, text_lower: str) -> bool:
    tv = (flow.trigger_value or "").strip().lower()
    if flow.trigger_type == BotFlow.TriggerType.KEYWORD:
        return bool(tv) and tv in text_lower
    if flow.trigger_type == BotFlow.TriggerType.MENU_SELECTION:
        return bool(tv) and text_lower == tv
    if flow.trigger_type == BotFlow.TriggerType.BUTTON_CLICK:
        return bool(tv) and text_lower == tv
    if flow.trigger_type in {
        BotFlow.TriggerType.CART_ACTION,
        BotFlow.TriggerType.PAYMENT_CONFIRMATION,
        BotFlow.TriggerType.ORDER_STATUS,
        BotFlow.TriggerType.BROADCAST_TRIGGER,
    }:
        return bool(tv) and tv in text_lower
    return False


def _run_flow_actions(*, owner, account: WhatsAppAccount, bot: Bot, customer: Customer, text: str, flow: BotFlow) -> EngineResult:
    replies: list[str] = []
    attachments: list[dict[str, Any]] = []
    for action in (flow.actions or []):
        if not isinstance(action, dict):
            continue
        typ = str(action.get("type") or "").strip().lower()

        if typ == "run_order_bot":
            res = handle_whatsapp_order_message(
                owner=owner,
                whatsapp_account=account,
                mobile_number=customer.phone_number,
                message=text,
                customer_name=customer.display_name,
                address=(getattr(customer.party, "address", "") if customer.party_id else ""),
            )
            replies.append(res.reply)
            return EngineResult(
                ok=res.ok,
                reply="\n".join([r for r in replies if r]),
                intent="order_bot",
                order_id=res.order_id,
                invoice_id=res.invoice_id,
                payment_url=res.payment_url,
                invoice_pdf_url=res.invoice_pdf_url,
                attachments=tuple(attachments),
            )

        if typ == "ai_reply":
            party = customer.party if customer.party_id else None
            reply = smart_reply(owner=owner, party=party, message=text) or ""
            if reply:
                replies.append(reply)
                return EngineResult(ok=True, reply="\n".join(replies), intent="ai_reply")
            continue

        if typ == "send_text":
            t = str(action.get("text") or "").strip()
            if t:
                replies.append(t)
            continue

        if typ == "send_message_key":
            key = str(action.get("key") or "").strip()
            if not key:
                continue
            msg = BotMessage.objects.filter(bot=bot, key=key).first()
            if not msg:
                continue
            if msg.message_type == BotMessage.MessageType.TEXT:
                if (msg.text or "").strip():
                    replies.append((msg.text or "").strip())
                continue
            if msg.message_type in {BotMessage.MessageType.IMAGE, BotMessage.MessageType.DOCUMENT} and (msg.media_url or "").strip():
                attachments.append(
                    {
                        "type": msg.message_type,
                        "link": (msg.media_url or "").strip(),
                        "filename": (msg.filename or "").strip(),
                        "caption": (msg.text or "").strip(),
                    }
                )
            continue

        if typ == "connect_human":
            replies.append("Support: Please share your issue. A human agent will contact you shortly.")
            continue

    return EngineResult(ok=True, reply="\n".join([r for r in replies if r]), intent="flow", attachments=tuple(attachments))


@transaction.atomic
def generate_reply(*, owner, account: WhatsAppAccount, customer: Customer, inbound_text: str) -> EngineResult:
    inbound_text = _norm(inbound_text)
    if not inbound_text:
        return EngineResult(ok=False, reply="", intent="empty")

    try:
        bot = account.bot  # type: ignore[attr-defined]
    except Exception:
        bot = None
    if not bot or not isinstance(bot, Bot):
        return EngineResult(ok=False, reply="", intent="no_bot")
    if not bot.is_enabled:
        return EngineResult(ok=False, reply="", intent="bot_disabled")
    if not bot.auto_reply_enabled:
        return EngineResult(ok=False, reply="", intent="auto_reply_disabled")

    text_lower = inbound_text.lower()

    # 1) No-code flows (highest priority)
    flows = list(bot.flows.filter(is_active=True).order_by("priority", "created_at")[:100])
    for flow in flows:
        if _match_flow(flow, text_lower):
            try:
                res = _run_flow_actions(owner=owner, account=account, bot=bot, customer=customer, text=inbound_text, flow=flow)
                if res.reply or res.attachments or res.invoice_pdf_url:
                    return res
            except Exception:
                logger.exception("Bot flow execution failed")
                continue

    # 1.5) Visual flow builder (drag & drop, per WhatsApp account)
    try:
        from whatsapp.services.visual_flow_engine import generate_visual_flow_reply

        visual = generate_visual_flow_reply(owner=owner, account=account, customer=customer, inbound_text=inbound_text)
        if visual:
            return EngineResult(ok=True, reply=visual, intent="visual_flow")
    except Exception:
        logger.exception("Visual flow engine failed")

    # 2) Built-in templates
    if bot.kind == Bot.Kind.WELCOME:
        return EngineResult(ok=True, reply="Hi! Type 'help' to see options.", intent="welcome")

    if bot.kind == Bot.Kind.SUPPORT:
        return EngineResult(ok=True, reply="Support: Please share your issue. A human agent will contact you shortly.", intent="support")

    if bot.kind in {Bot.Kind.ORDER, Bot.Kind.PAYMENT, Bot.Kind.CUSTOM}:
        res: ConversationResult = handle_whatsapp_order_message(
            owner=owner,
            whatsapp_account=account,
            mobile_number=customer.phone_number,
            message=inbound_text,
            customer_name=customer.display_name,
            address=(getattr(customer.party, "address", "") if customer.party_id else ""),
        )
        if res.reply:
            return EngineResult(
                ok=res.ok,
                reply=res.reply,
                intent=res.mode or "order_bot",
                order_id=res.order_id,
                invoice_id=res.invoice_id,
                payment_url=res.payment_url,
                invoice_pdf_url=res.invoice_pdf_url,
            )

    # 3) AI fallback (rule-based)
    if bot.ai_fallback_enabled:
        party: Optional[Party] = customer.party if customer.party_id else None
        reply = smart_reply(owner=owner, party=party, message=inbound_text)
        if reply:
            return EngineResult(ok=True, reply=reply, intent="ai_fallback")

    return EngineResult(ok=True, reply="Type 'help' for menu.", intent="fallback")
