from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from storefront.models import VendorProductListing
from saas.utils.pricing import quote_price, resolve_store_type


SESSION_KEY = "storefront_cart_v1"


@dataclass
class SessionCartItem:
    listing_id: int
    qty: int


def _get_cart_root(session) -> dict:
    root = session.get(SESSION_KEY)
    if not isinstance(root, dict):
        root = {}
        session[SESSION_KEY] = root
    return root


def get_vendor_cart(session, vendor_id: int) -> dict:
    root = _get_cart_root(session)
    vendor_key = str(int(vendor_id))
    cart = root.get(vendor_key)
    if not isinstance(cart, dict):
        cart = {"items": {}, "coupon": {}, "updated_at": timezone.now().isoformat()}
        root[vendor_key] = cart
        session[SESSION_KEY] = root
    if not isinstance(cart.get("coupon"), dict):
        cart["coupon"] = {}
    return cart


def add_item(session, *, vendor_id: int, listing_id: int, qty: int = 1) -> None:
    cart = get_vendor_cart(session, vendor_id)
    items = cart.get("items") if isinstance(cart.get("items"), dict) else {}
    key = str(int(listing_id))
    current = int(items.get(key) or 0)
    items[key] = max(1, current + max(1, int(qty or 1)))
    cart["items"] = items
    cart["updated_at"] = timezone.now().isoformat()
    session.modified = True


def set_qty(session, *, vendor_id: int, listing_id: int, qty: int) -> None:
    cart = get_vendor_cart(session, vendor_id)
    items = cart.get("items") if isinstance(cart.get("items"), dict) else {}
    key = str(int(listing_id))
    if qty <= 0:
        items.pop(key, None)
    else:
        items[key] = int(qty)
    cart["items"] = items
    cart["updated_at"] = timezone.now().isoformat()
    session.modified = True


def clear_vendor_cart(session, vendor_id: int) -> None:
    root = _get_cart_root(session)
    root.pop(str(int(vendor_id)), None)
    session[SESSION_KEY] = root
    session.modified = True


def set_vendor_coupon_code(session, *, vendor_id: int, code: str) -> None:
    cart = get_vendor_cart(session, vendor_id)
    cart["coupon"] = {"code": (code or "").strip().upper()}
    cart["updated_at"] = timezone.now().isoformat()
    session.modified = True


def clear_vendor_coupon(session, *, vendor_id: int) -> None:
    cart = get_vendor_cart(session, vendor_id)
    cart["coupon"] = {}
    cart["updated_at"] = timezone.now().isoformat()
    session.modified = True


def build_cart_view(*, vendor, session, user=None) -> dict:
    cart = get_vendor_cart(session, vendor.id)
    items_map = cart.get("items") if isinstance(cart.get("items"), dict) else {}
    coupon_blob = cart.get("coupon") if isinstance(cart.get("coupon"), dict) else {}
    coupon_code = (coupon_blob.get("code") or "").strip().upper()
    listing_ids = [int(k) for k in items_map.keys() if str(k).isdigit()]

    store_type = resolve_store_type(user) if user is not None else "b2c"
    is_b2b_user = store_type in {"b2b", "hybrid"} and store_type != "b2c"
    listings = list(
        VendorProductListing.objects.select_related("product", "product__category")
        .filter(vendor=vendor, id__in=listing_ids, is_online=True)
    )
    if not is_b2b_user:
        listings = [l for l in listings if not getattr(l.product, "is_b2b_only", False)]
    listing_by_id = {l.id: l for l in listings}
    rows = []
    subtotal = Decimal("0.00")
    total_qty = 0
    for lid in listing_ids:
        listing = listing_by_id.get(lid)
        if not listing:
            continue
        qty = int(items_map.get(str(lid)) or 0)
        if qty <= 0:
            continue
        p = listing.product
        quote = quote_price(
            base_b2c_price=Decimal(str(getattr(p, "b2c_price", "0") or "0")),
            base_b2b_price=Decimal(str(getattr(p, "b2b_price", "0") or "0")) if getattr(p, "b2b_price", None) is not None else None,
            qty=qty,
            moq=int(getattr(p, "moq", 1) or 1),
            is_b2b_only=bool(getattr(p, "is_b2b_only", False)),
            user_store_type=store_type,
            bulk_price=Decimal(str(getattr(p, "bulk_price", "0") or "0")) if getattr(p, "bulk_price", None) is not None else None,
            bulk_qty=int(getattr(p, "bulk_qty", 0) or 0),
            mrp=Decimal(str(getattr(p, "mrp", "0") or "0")) if getattr(p, "mrp", None) is not None else None,
        )
        unit = Decimal(str(listing.price_override or quote.unit_price or "0"))
        line = (unit * Decimal(qty)).quantize(Decimal("0.01"))
        subtotal += line
        total_qty += qty
        rows.append(
            {
                "listing": listing,
                "qty": qty,
                "unit_price": unit,
                "line_total": line,
                "is_b2b": quote.is_b2b,
                "moq": quote.moq,
            }
        )
    return {"rows": rows, "subtotal": subtotal, "total_qty": total_qty, "coupon_code": coupon_code}
