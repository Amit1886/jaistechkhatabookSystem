from __future__ import annotations

import logging
import re
from typing import Optional

from django.utils import timezone

from commerce.services.whatsapp_conversation import handle_whatsapp_order_message
from whatsapp.models import Customer, VisualFlow, VisualEdge, WhatsAppAccount
from whatsapp.services.smart_reply import smart_reply

logger = logging.getLogger(__name__)

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "").strip()).strip()


def _pick_edge(*, flow: VisualFlow, node_id: str, message_lower: str) -> Optional[VisualEdge]:
    edges = list(flow.edges.filter(source_id=node_id).order_by("id"))
    if not edges:
        return None

    for e in edges:
        cond = (e.condition_text or "").strip().lower()
        if cond and cond in message_lower:
            return e

    for e in edges:
        if bool(e.is_default):
            return e

    # Deterministic fallback (first)
    return edges[0]


def generate_visual_flow_reply(
    *,
    owner,
    account: WhatsAppAccount,
    customer: Customer,
    inbound_text: str,
) -> Optional[str]:
    """
    Runs the user-side visual flow builder for this WhatsAppAccount.

    Returns a reply text when a matching edge is found, else None.
    """
    text = _norm(inbound_text)
    if not text:
        return None
    message_lower = text.lower()

    flow = (
        VisualFlow.objects.filter(owner=owner, whatsapp_account=account, is_active=True)
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if not flow:
        return None

    start = flow.nodes.filter(node_type=VisualFlow.NodeType.START).first() or flow.nodes.filter(node_id="start").first()
    if not start:
        return None

    cursor_node_id = (customer.visual_flow_node_id or "").strip()
    if customer.active_visual_flow_id != flow.id or not cursor_node_id:
        cursor_node_id = start.node_id

    cursor = flow.nodes.filter(node_id=cursor_node_id).first() or start
    if cursor.node_type == VisualFlow.NodeType.END:
        cursor = start

    edge = _pick_edge(flow=flow, node_id=cursor.node_id, message_lower=message_lower)
    if not edge and cursor.node_id != start.node_id:
        edge = _pick_edge(flow=flow, node_id=start.node_id, message_lower=message_lower)
    if not edge:
        return None

    node = flow.nodes.filter(node_id=edge.target_id).first()
    steps = 0
    while node and steps < 15:
        steps += 1
        if node.node_type in {VisualFlow.NodeType.START, VisualFlow.NodeType.CONDITION}:
            nxt = _pick_edge(flow=flow, node_id=node.node_id, message_lower=message_lower)
            if not nxt:
                return None
            node = flow.nodes.filter(node_id=nxt.target_id).first()
            continue

        data = node.data or {}
        reply = ""

        if node.node_type == VisualFlow.NodeType.ACTION:
            action = str(data.get("action") or data.get("action_type") or "").strip().lower()
            if action in {"show_catalog", "catalog", "products"}:
                res = handle_whatsapp_order_message(
                    owner=owner,
                    whatsapp_account=account,
                    mobile_number=customer.phone_number,
                    message="products",
                    customer_name=customer.display_name,
                    address=(getattr(customer.party, "address", "") if customer.party_id else ""),
                )
                reply = res.reply or ""
            elif action in {"show_cart", "cart"}:
                res = handle_whatsapp_order_message(
                    owner=owner,
                    whatsapp_account=account,
                    mobile_number=customer.phone_number,
                    message="cart",
                    customer_name=customer.display_name,
                    address=(getattr(customer.party, "address", "") if customer.party_id else ""),
                )
                reply = res.reply or ""
            elif action in {"checkout"}:
                res = handle_whatsapp_order_message(
                    owner=owner,
                    whatsapp_account=account,
                    mobile_number=customer.phone_number,
                    message="checkout",
                    customer_name=customer.display_name,
                    address=(getattr(customer.party, "address", "") if customer.party_id else ""),
                )
                reply = res.reply or ""
            elif action in {"my_orders", "orders"}:
                res = handle_whatsapp_order_message(
                    owner=owner,
                    whatsapp_account=account,
                    mobile_number=customer.phone_number,
                    message="orders",
                    customer_name=customer.display_name,
                    address=(getattr(customer.party, "address", "") if customer.party_id else ""),
                )
                reply = res.reply or ""
            elif action in {"track_order", "track"}:
                res = handle_whatsapp_order_message(
                    owner=owner,
                    whatsapp_account=account,
                    mobile_number=customer.phone_number,
                    message="track",
                    customer_name=customer.display_name,
                    address=(getattr(customer.party, "address", "") if customer.party_id else ""),
                )
                reply = res.reply or ""
            elif action in {"ai_reply"}:
                party = customer.party if customer.party_id else None
                reply = smart_reply(owner=owner, party=party, message=inbound_text) or ""
            elif action in {"handoff_human", "connect_human", "support"}:
                reply = "Support: Please share your issue. A human agent will contact you shortly."
            elif action in {"send_message", "send_text"}:
                reply = str(data.get("text") or "").strip()
            else:
                # Backward compatible: action node behaves like a message node when no action is configured.
                reply = str(data.get("text") or "").strip()
        else:
            reply = str(data.get("text") or "").strip()

        if not reply:
            return None

        # Persist cursor to support multi-step flows.
        customer.active_visual_flow = flow
        customer.visual_flow_node_id = node.node_id
        customer.visual_flow_updated_at = timezone.now()
        customer.save(update_fields=["active_visual_flow", "visual_flow_node_id", "visual_flow_updated_at", "updated_at"])
        return reply

    return None
