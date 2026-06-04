from __future__ import annotations

import secrets
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import math
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from chatbot.services.flow_engine import run_flow
from commerce.models import (
    Category,
    Invoice,
    Order,
    OrderItem,
    Product,
    WhatsAppCartItem,
    WhatsAppOrderInbox,
    WhatsAppSession,
)
from commerce.services.whatsapp_orders import parse_whatsapp_order_message
from khataapp.models import Party


PAYMENT_MODES = {
    "cash": "Cash",
    "paytm": "Paytm",
    "cod": "Cash on Delivery",
    "netbanking": "Netbanking",
    "upi": "UPI",
    "card": "Card",
    "wallet": "Wallet",
}


@dataclass(frozen=True)
class ConversationResult:
    ok: bool
    reply: str
    mode: str = "order_bot"
    order_id: Optional[int] = None
    invoice_id: Optional[int] = None
    payment_url: str = ""
    invoice_pdf_url: str = ""


_WS = re.compile(r"\s+")


def _digits(s: str) -> str:
    return re.sub(r"[^0-9]", "", s or "")


def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "").strip()).strip()


def _wa_help_text() -> str:
    return (
        "Welcome! Reply with:\n"
        "1 View Products\n"
        "2 Place Order\n"
        "3 My Orders\n"
        "4 Customer Support\n"
        "5 Offers\n"
        "6 Track Delivery\n\n"
        "Quick commands:\n"
        "[products] [cart] [checkout]\n"
        "- category <name>\n"
        "- add <qty> <product>\n"
        "- remove <product>\n"
        "- update qty <product> <qty>\n"
        "- pay cash/upi/cod/netbanking"
    )


def _wa_categories_text(owner, party: Party) -> str:
    categories = Category.objects.filter(owner=owner).order_by("name")
    if not categories.exists():
        categories = Category.objects.all().order_by("name")
    if not categories.exists():
        return "No categories found."

    cat_lines = "\n".join([f"- {c.name}" for c in categories])
    segment = party.customer_category or "General"
    return f"Customer segment: {segment}\nCategories:\n{cat_lines}\nQuick: [category <name>] [cart]"


def _wa_products_in_category(owner, category_name: str) -> str:
    category_name = (category_name or "").strip()
    category = Category.objects.filter(owner=owner, name__iexact=category_name).first()
    if not category:
        category = Category.objects.filter(name__iexact=category_name).first()
    if not category:
        return "Category not found. Type 'products' to see categories."

    products = Product.objects.filter(category=category, owner=owner).order_by("name")
    if not products.exists():
        products = Product.objects.filter(category=category).order_by("name")
    if not products.exists():
        return f"No products in {category.name}."

    lines = "\n".join([f"- {p.name} (Rs. {p.price})" for p in products[:80]])
    more = "\n..." if products.count() > 80 else ""
    return f"{category.name} products:\n{lines}{more}\nQuick: [add <qty> <product>] [cart]"


def _wa_cart_text(session: WhatsAppSession) -> str:
    items = session.cart_items.select_related("product")
    if not items.exists() and not session.unmatched_items:
        return "Your cart is empty. Type 'products' to browse."

    lines: list[str] = []
    total = Decimal("0.00")
    for item in items:
        line_total = item.quantity * item.unit_price
        total += line_total
        lines.append(f"- {item.product.name} x {item.quantity} = Rs. {line_total}")

    for item in session.unmatched_items:
        lines.append(f"- {item.get('name')} x {item.get('qty')} (manual review)")

    lines.append(f"Total: Rs. {total}")
    lines.append("Type 'checkout' to place order.")
    return "\n".join(lines)


def _wa_strip_verbs(text: str) -> str:
    lower = (text or "").lower().strip()
    for verb in ["add ", "order ", "buy ", "need ", "want "]:
        if lower.startswith(verb):
            return (text or "")[len(verb) :].strip()
    return (text or "").strip()


def _ensure_party(*, owner, mobile_number: str, customer_name: str = "", address: str = "") -> Party:
    mobile_number = (mobile_number or "").strip()
    party = Party.objects.filter(Q(whatsapp_number=mobile_number) | Q(mobile=mobile_number), owner=owner).order_by("-id").first()
    if party:
        # Backfill WhatsApp number if missing.
        if not (party.whatsapp_number or "").strip():
            party.whatsapp_number = mobile_number
            party.save(update_fields=["whatsapp_number"])
        return party
    return Party.objects.create(
        owner=owner,
        name=(customer_name or f"WhatsApp Customer {mobile_number[-4:]}").strip()[:100],
        mobile=mobile_number,
        whatsapp_number=mobile_number,
        address=(address or "").strip(),
        party_type="customer",
    )


def _map_menu_selection(text_lower: str) -> str:
    return {
        "1": "products",
        "2": "products",
        "3": "my_orders",
        "4": "support",
        "5": "offers",
        "6": "track",
    }.get(text_lower, "")


def _my_orders_text(*, owner, party: Party) -> str:
    orders = (
        Order.objects.filter(owner=owner, party=party)
        .order_by("-created_at", "-id")
        .only("id", "status", "created_at")[:5]
    )
    if not orders:
        return "No orders yet. Type 'products' to browse."
    lines = [f"- Order #{o.id}: {o.status} ({o.created_at.strftime('%d %b %H:%M')})" for o in orders]
    return "Your recent orders:\n" + "\n".join(lines) + "\nType 'track' to see latest status."


def _latest_order_status_text(*, owner, party: Party) -> str:
    order = Order.objects.filter(owner=owner, party=party).order_by("-created_at", "-id").first()
    if not order:
        return "No orders found. Type 'products' to browse."
    return f"Latest order: #{order.id}\nStatus: {order.status}"


def _maybe_create_payment_link(*, owner, invoice: Invoice, provider: str) -> tuple[str, str]:
    """
    Create a public PaymentLink (and its public invoice PDF URL) if the portal app is available.
    Returns (pay_url, pdf_url). Empty strings when unavailable.
    """
    base_url = (getattr(settings, "BASE_URL", "") or "").strip().rstrip("/")
    if not base_url:
        return "", ""

    try:
        from portal.models import PaymentLink
    except Exception:
        return "", ""

    amount = invoice.amount or Decimal("0.00")
    expires_at = timezone.now() + timedelta(days=2)

    link = None
    for _ in range(5):
        token = secrets.token_hex(32)
        try:
            link = PaymentLink.objects.create(
                owner=owner,
                invoice=invoice,
                token=token,
                amount=amount,
                provider=(provider or "upi")[:40],
                expires_at=expires_at,
            )
            break
        except Exception:
            link = None
            continue

    if not link:
        return "", ""

    pay_url = f"{base_url}/portal/pay/{link.token}/"
    pdf_url = f"{base_url}/portal/pay/{link.token}/invoice.pdf"
    return pay_url, pdf_url


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _quick_radius_check(*, owner, whatsapp_account, mobile: str) -> tuple[bool, Optional[float], Optional[float]]:
    """
    Returns (within_radius, dist_km, radius_km).

    - If quick mode is disabled or radius is not configured, returns (True, None, None).
    - If radius is configured but customer location is missing, returns (False, None, radius_km).
    """
    quick_enabled = bool(getattr(whatsapp_account, "quick_commerce_enabled", False)) if whatsapp_account else False
    if not (quick_enabled and whatsapp_account):
        return True, None, None
    try:
        radius = float(getattr(whatsapp_account, "quick_delivery_radius_km", 0) or 0)
        s_lat = getattr(whatsapp_account, "store_latitude", None)
        s_lng = getattr(whatsapp_account, "store_longitude", None)
        if radius <= 0 or s_lat is None or s_lng is None:
            return True, None, radius if radius > 0 else None

        from whatsapp.models import Customer  # local import (optional dependency)

        cust = (
            Customer.objects.filter(owner=owner, whatsapp_account=whatsapp_account)
            .filter(phone_number__endswith=mobile)
            .order_by("-last_location_at", "-updated_at")
            .first()
        )
        if not cust or cust.last_location_lat is None or cust.last_location_lng is None:
            return False, None, radius

        dist_km = _haversine_km(float(s_lat), float(s_lng), float(cust.last_location_lat), float(cust.last_location_lng))
        return dist_km <= radius, dist_km, radius
    except Exception:
        return True, None, None


@transaction.atomic
def handle_whatsapp_order_message(
    *,
    owner,
    whatsapp_account=None,
    mobile_number: str,
    message: str,
    customer_name: str = "",
    address: str = "",
) -> ConversationResult:
    """
    Multi-tenant WhatsApp commerce conversation handler.

    This function is provider-agnostic (Cloud API / Web Gateway) and only returns the reply text.
    """
    message = _norm(message)
    mobile_raw = (mobile_number or "").strip()
    d = _digits(mobile_raw)
    mobile = (d[-10:] if len(d) > 10 else d) or mobile_raw
    if not mobile or not message:
        return ConversationResult(ok=False, reply="mobile and message are required")

    party = _ensure_party(owner=owner, mobile_number=mobile, customer_name=customer_name, address=address)

    session, _ = WhatsAppSession.objects.get_or_create(
        owner=owner,
        whatsapp_account=whatsapp_account,
        mobile_number=mobile,
        defaults={"party": party},
    )
    if not session.party_id:
        session.party = party
        session.save(update_fields=["party"])

    text = message.strip()
    text_lower = text.lower()

    mapped = _map_menu_selection(text_lower)
    if mapped:
        text_lower = mapped

    if text_lower == "location":
        within, dist_km, radius = _quick_radius_check(owner=owner, whatsapp_account=whatsapp_account, mobile=mobile)
        if session.state == "awaiting_payment":
            if bool(getattr(whatsapp_account, "quick_commerce_enabled", False)) and radius:
                if within:
                    return ConversationResult(ok=True, reply=f"Location received (within {radius:.0f} km). Now select payment mode: cash, upi, cod, netbanking, card, wallet")
                if dist_km is not None:
                    return ConversationResult(ok=True, reply=f"Location received, but outside delivery radius (approx {dist_km:.1f} km). Please contact support.")
                return ConversationResult(ok=True, reply="Location received. Now select payment mode: cash, upi, cod, netbanking, card, wallet")
            return ConversationResult(ok=True, reply="Location received. Now select payment mode: cash, upi, cod, netbanking, card, wallet")
        if bool(getattr(whatsapp_account, "quick_commerce_enabled", False)) and radius:
            if within:
                return ConversationResult(ok=True, reply=f"Location received (within {radius:.0f} km). Type 'checkout' to continue.")
            if dist_km is not None:
                return ConversationResult(ok=True, reply=f"Location received, but outside delivery radius (approx {dist_km:.1f} km).")
        return ConversationResult(ok=True, reply="Location received. Type 'checkout' to continue.")

    if text_lower in {"hi", "hello", "start", "menu", "help"}:
        return ConversationResult(ok=True, reply=_wa_help_text())

    if text_lower in {"products", "product list", "catalog", "list"}:
        if session.state != "browsing":
            session.state = "browsing"
            session.save(update_fields=["state"])
        return ConversationResult(ok=True, reply=_wa_categories_text(owner, party))

    if text_lower.startswith("category "):
        if session.state != "browsing":
            session.state = "browsing"
            session.save(update_fields=["state"])
        category_name = text[9:].strip()
        return ConversationResult(ok=True, reply=_wa_products_in_category(owner, category_name))

    if text_lower in {"cart", "my cart", "basket", "view cart", "view"}:
        return ConversationResult(ok=True, reply=_wa_cart_text(session))

    if text_lower in {"my_orders", "my orders", "orders"}:
        return ConversationResult(ok=True, reply=_my_orders_text(owner=owner, party=party))

    if text_lower in {"support", "customer support"}:
        return ConversationResult(ok=True, reply="Support: Please share your issue. A human agent will contact you shortly.")

    if text_lower in {"offers", "offer"}:
        return ConversationResult(ok=True, reply="Offers: Check the latest discounts in our catalog. Type 'products' to browse.")

    if text_lower in {"track", "track delivery", "order status", "status"}:
        return ConversationResult(ok=True, reply=_latest_order_status_text(owner=owner, party=party))

    if text_lower in {"checkout", "place order", "submit", "order submit"}:
        if not session.cart_items.exists() and not session.unmatched_items:
            return ConversationResult(ok=True, reply="Your cart is empty. Add items first.")
        session.state = "awaiting_payment"
        session.save(update_fields=["state"])
        return ConversationResult(ok=True, reply="Select payment mode: cash, upi, cod, netbanking, card, wallet")

    if text_lower.startswith("update qty "):
        if session.state != "browsing":
            session.state = "browsing"
            session.save(update_fields=["state"])
        # update qty <product> <qty>
        remainder = text[len("update qty ") :].strip()
        parts = remainder.rsplit(" ", 1)
        if len(parts) != 2:
            return ConversationResult(ok=True, reply="Usage: update qty <product> <qty>")
        prod_name, qty_raw = parts[0].strip(), parts[1].strip()
        try:
            qty = int(qty_raw)
        except Exception:
            qty = 0
        if qty <= 0:
            return ConversationResult(ok=True, reply="Qty must be > 0")
        products = Product.objects.filter(owner=owner)
        if not products.exists():
            products = Product.objects.all()
        parsed = parse_whatsapp_order_message(prod_name, products)
        if parsed and parsed[0].matched_product:
            p = parsed[0].matched_product
            item = WhatsAppCartItem.objects.filter(session=session, product=p).first()
            if not item:
                return ConversationResult(ok=True, reply="Item not in cart. Type 'products' to browse.")
            item.quantity = qty
            item.save(update_fields=["quantity"])
            return ConversationResult(ok=True, reply="Updated. Type 'cart' to view.")
        return ConversationResult(ok=True, reply="Product not found. Type 'products' to browse.")

    if text_lower in PAYMENT_MODES:
        if session.state != "awaiting_payment":
            return ConversationResult(ok=True, reply="Type 'checkout' to select payment mode.")

        session.selected_payment_mode = text_lower
        session.save(update_fields=["selected_payment_mode"])

        quick_enabled = bool(getattr(whatsapp_account, "quick_commerce_enabled", False)) if whatsapp_account else False
        within_radius, dist_km, radius = _quick_radius_check(owner=owner, whatsapp_account=whatsapp_account, mobile=mobile)

        initial_status = "accepted" if (quick_enabled and within_radius) else "pending"

        order = Order.objects.create(
            owner=owner,
            party=party,
            order_type="SALE",
            status=initial_status,
            notes=f"WhatsApp order from {mobile}",
            order_source="WhatsApp",
        )
        if quick_enabled and within_radius:
            try:
                qa = getattr(whatsapp_account, "quick_assign_agent", None)
                if qa:
                    order.agent = qa
                    order.assigned_to = getattr(qa, "user", None)
                    order.save(update_fields=["agent", "assigned_to"])
            except Exception:
                pass

        for item in session.cart_items.select_related("product"):
            OrderItem.objects.create(
                order=order,
                product=item.product,
                qty=item.quantity,
                price=item.unit_price,
            )

        for item in session.unmatched_items:
            OrderItem.objects.create(
                order=order,
                product=None,
                qty=item.get("qty", 1),
                price=Decimal("0.00"),
                raw_name=item.get("name", "Unknown"),
            )

        # Smart BI: Festival Sale Mode (auto-discount) - best effort.
        try:
            from smart_bi.services.festival import apply_festival_discount

            apply_festival_discount(order, save=True)
        except Exception:
            pass

        invoice = Invoice.objects.create(order=order)
        pay_url, pdf_url = _maybe_create_payment_link(owner=owner, invoice=invoice, provider=text_lower)

        inbox_status = "new" if not session.unmatched_items else "manual_review"
        WhatsAppOrderInbox.objects.create(
            owner=owner,
            whatsapp_account=whatsapp_account,
            party=party,
            mobile_number=mobile,
            customer_name=party.name,
            raw_message=message,
            parsed_items=[
                {
                    "raw_name": item.product.name,
                    "quantity": item.quantity,
                    "matched": True,
                    "product_id": item.product.id,
                    "confidence": 1.0,
                    "status": "matched",
                }
                for item in session.cart_items.select_related("product")
            ]
            + [
                {
                    "raw_name": item.get("name", "Unknown"),
                    "quantity": item.get("qty", 1),
                    "matched": False,
                    "product_id": None,
                    "confidence": 0.0,
                    "status": "manual_review",
                }
                for item in session.unmatched_items
            ],
            status=inbox_status,
            order=order,
        )

        session.cart_items.all().delete()
        session.unmatched_items = []
        session.state = "completed"
        session.save(update_fields=["unmatched_items", "state"])

        lines = [
            f"Order #{order.id} placed.",
            f"Total Rs. {order.total_amount()}.",
            f"Payment mode: {PAYMENT_MODES[text_lower]}.",
        ]
        if quick_enabled and within_radius:
            lines.append("Quick mode: order confirmed.")
        elif quick_enabled and not within_radius:
            if dist_km is not None:
                lines.append(f"Quick mode: outside delivery radius (approx {dist_km:.1f} km).")
            else:
                lines.append("Quick mode: share your location to confirm delivery radius.")
        if pay_url and text_lower not in {"cash", "cod"}:
            lines.append(f"Pay here: {pay_url}")
        if pdf_url:
            lines.append(f"Invoice PDF: {pdf_url}")

        return ConversationResult(
            ok=True,
            reply="\n".join(lines),
            order_id=order.id,
            invoice_id=invoice.id,
            payment_url=pay_url,
            invoice_pdf_url=pdf_url,
        )

    if text_lower.startswith("remove "):
        if session.state != "browsing":
            session.state = "browsing"
            session.save(update_fields=["state"])
        remove_text = _wa_strip_verbs(text)
        products = Product.objects.filter(owner=owner)
        if not products.exists():
            products = Product.objects.all()
        parsed = parse_whatsapp_order_message(remove_text, products)
        if parsed and parsed[0].matched_product:
            WhatsAppCartItem.objects.filter(session=session, product=parsed[0].matched_product).delete()
            return ConversationResult(ok=True, reply="Removed item. Type 'cart' to view.")
        return ConversationResult(ok=True, reply="Product not found in cart.")

    if text_lower in {"clear cart", "clear", "empty cart"}:
        if session.state != "browsing":
            session.state = "browsing"
            session.save(update_fields=["state"])
        session.cart_items.all().delete()
        session.unmatched_items = []
        session.save(update_fields=["unmatched_items"])
        return ConversationResult(ok=True, reply="Cart cleared. Type 'products' to browse.")

    # Parse as an order/add command
    if session.state != "browsing":
        session.state = "browsing"
        session.save(update_fields=["state"])

    cleaned = _wa_strip_verbs(text)
    products = Product.objects.filter(owner=owner)
    if not products.exists():
        products = Product.objects.all()
    parsed_items = parse_whatsapp_order_message(cleaned, products)

    matched = [p for p in parsed_items if p.matched_product]
    unmatched = [p for p in parsed_items if not p.matched_product]

    for p in matched:
        prod = p.matched_product
        if not prod:
            continue
        cart_item, _ = WhatsAppCartItem.objects.get_or_create(
            session=session,
            product=prod,
            defaults={"quantity": p.quantity, "unit_price": prod.price},
        )
        if not _:
            cart_item.quantity += p.quantity
            cart_item.save(update_fields=["quantity"])

    if unmatched:
        session.unmatched_items = (session.unmatched_items or []) + [{"name": u.raw_name, "qty": u.quantity} for u in unmatched]
        session.save(update_fields=["unmatched_items"])

    if matched or unmatched:
        added_lines = []
        if matched:
            added_lines.append("Added to cart:")
            for p in matched:
                added_lines.append(f"- {p.matched_product.name} x {p.quantity}")
        if unmatched:
            added_lines.append("Need manual review:")
            for u in unmatched:
                added_lines.append(f"- {u.raw_name} x {u.quantity}")
        added_lines.append("Type 'cart' to view, or 'checkout' to place order.")
        return ConversationResult(ok=True, reply="\n".join(added_lines))

    # Try custom chatbot flow (no-code builder can extend this later)
    flow_reply = run_flow(message)
    if flow_reply:
        return ConversationResult(ok=True, reply=flow_reply, mode="flow")

    return ConversationResult(ok=True, reply="Sorry, I could not understand. Type 'help' for options.")
