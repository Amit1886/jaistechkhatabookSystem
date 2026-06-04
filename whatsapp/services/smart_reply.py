from __future__ import annotations

import os
import re
from typing import Optional

from commerce.models import Order, Product
from khataapp.models import Party


_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "").strip()).strip()


def _looks_like_price_question(text_lower: str) -> bool:
    hints = [
        "price",
        "rate",
        "cost",
        "mrp",
        "kitna",
        "kitne",
        "daam",
        "bhaav",
        "bhav",
        "pricing",
    ]
    return any(h in text_lower for h in hints)


def _looks_like_status_question(text_lower: str) -> bool:
    hints = [
        "status",
        "track",
        "tracking",
        "delivery",
        "kahan",
        "kaha",
        "kab",
        "order",
        "my order",
    ]
    return any(h in text_lower for h in hints)


def _match_product(owner, query: str) -> Optional[Product]:
    query = (query or "").strip()
    if not query:
        return None
    qs = Product.objects.filter(owner=owner, name__icontains=query).order_by("name")
    p = qs.first()
    if p:
        return p
    # fallback: global product list (demo-friendly)
    return Product.objects.filter(name__icontains=query).order_by("name").first()


def _openai_client():
    try:
        from openai import OpenAI  # type: ignore

        return OpenAI()
    except Exception:
        return None


def _looks_like_general_question(text_lower: str) -> bool:
    hints = [
        "?",
        "help",
        "menu",
        "kya",
        "kaise",
        "kaisa",
        "kab",
        "kahan",
        "available",
        "timing",
        "address",
        "delivery",
    ]
    return any(h in text_lower for h in hints)


def _ai_enabled() -> bool:
    flag = (os.getenv("WHATSAPP_AI_ENABLED") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return False


def _ai_model() -> str:
    return (os.getenv("WHATSAPP_AI_MODEL") or "").strip() or "gpt-4o-mini"


def _ai_fallback_reply(*, owner, party: Optional[Party], message: str) -> Optional[str]:
    """
    Optional LLM fallback for Hindi+English questions.

    Controlled by env:
    - WHATSAPP_AI_ENABLED=true
    - OPENAI_API_KEY=<key>
    - WHATSAPP_AI_MODEL=gpt-4o-mini (optional)
    """
    if not _ai_enabled():
        return None
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        return None

    client = _openai_client()
    if not client:
        return None

    text = _norm(message)
    if not text:
        return None

    latest_order_line = ""
    if party:
        o = Order.objects.filter(owner=owner, party=party).order_by("-created_at", "-id").first()
        if o:
            latest_order_line = f"Latest order: #{o.id} status={o.status}"

    # Try to pick a simple product hint from the message.
    words = re.sub(r"[^a-zA-Z0-9 ]+", " ", text).split()
    words = [w for w in words if len(w) >= 3]
    query = max(words, key=len) if words else ""

    product_lines: list[str] = []
    if query:
        qs = Product.objects.filter(owner=owner, name__icontains=query).order_by("name")[:5]
        if not qs.exists():
            qs = Product.objects.filter(name__icontains=query).order_by("name")[:5]
        for p in qs:
            product_lines.append(f"- {p.name}: Rs. {p.price}")

    context_lines = []
    if latest_order_line:
        context_lines.append(latest_order_line)
    if product_lines:
        context_lines.append("Products:")
        context_lines.extend(product_lines)
    context = "\n".join(context_lines).strip()

    try:
        resp = client.chat.completions.create(
            model=_ai_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a WhatsApp commerce assistant for an Indian small business. "
                        "Reply in concise Hinglish (Hindi+English). "
                        "Only use the provided context for prices/order status; if missing, ask the user to type 'products' or 'track'."
                    ),
                },
                {"role": "user", "content": f"Customer message:\n{text}\n\nContext:\n{context or '(none)'}"},
            ],
            temperature=0.2,
        )
        out = ""
        try:
            out = (resp.choices[0].message.content or "").strip()
        except Exception:
            out = ""
        return out or None
    except Exception:
        return None


def smart_reply(*, owner, party: Optional[Party], message: str) -> Optional[str]:
    """
    Lightweight Hindi+English smart replies without calling external LLMs.
    """
    text = _norm(message)
    if not text:
        return None
    text_lower = text.lower()

    if party and _looks_like_status_question(text_lower):
        order = Order.objects.filter(owner=owner, party=party).order_by("-created_at", "-id").first()
        if not order:
            return "No orders found. Type 'products' to browse."
        return f"Latest order #{order.id} status: {order.status}"

    if _looks_like_price_question(text_lower):
        # naive extraction: remove obvious words
        cleaned = re.sub(r"\b(price|rate|cost|mrp|kitna|kitne|daam|bhav|bhaav)\b", " ", text_lower, flags=re.IGNORECASE)
        cleaned = _norm(cleaned)
        product = _match_product(owner, cleaned)
        if product:
            return f"{product.name} price: Rs. {product.price}"
        return "Product not found. Type 'products' to browse the catalog."

    # Optional LLM fallback for general questions.
    if _looks_like_general_question(text_lower):
        ai = _ai_fallback_reply(owner=owner, party=party, message=text)
        if ai:
            return ai

    return None
