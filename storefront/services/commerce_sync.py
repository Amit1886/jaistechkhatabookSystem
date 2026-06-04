from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q


def _safe_decimal(v) -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0.00")


@transaction.atomic
def ensure_commerce_order_for_store_order(*, store_order):
    """
    Ensure a `commerce.Order` exists for this `storefront.StoreOrder`.

    Purpose: centralize all orders under `/commerce/orders/sales/` so that
    accept/reject and ledger/voucher flows remain centralized.
    """
    if getattr(store_order, "commerce_order_id", None):
        return store_order.commerce_order

    from commerce.models import Order as CommerceOrder, OrderItem as CommerceOrderItem
    from khataapp.models import Party

    vendor = store_order.vendor
    owner = getattr(vendor, "owner", None)
    if not owner:
        raise ValueError("Vendor owner missing")

    customer_user = store_order.customer
    mobile = (getattr(customer_user, "mobile", None) or "").strip()
    email = (getattr(customer_user, "email", None) or "").strip()
    name = (
        (getattr(getattr(customer_user, "customer_profile", None), "full_name", None) or "").strip()
        or (getattr(customer_user, "get_full_name", lambda: "")() or "").strip()
        or (getattr(customer_user, "username", None) or "").strip()
        or email
        or mobile
        or "Online Customer"
    )

    party_q = Q(owner=owner, party_type="customer")
    if mobile:
        party_q &= Q(mobile=mobile)
    elif email:
        party_q &= Q(email=email)
    else:
        party_q &= Q(name=name)

    party = Party.objects.filter(party_q).order_by("-id").first()
    if not party:
        party = Party.objects.create(
            owner=owner,
            party_type="customer",
            name=name[:100],
            mobile=mobile[:15],
            email=email[:254],
            address=(getattr(getattr(store_order, "address", None), "line1", "") or "")[:400],
            pincode_text=(getattr(getattr(store_order, "address", None), "pincode", "") or "")[:12],
        )

    # Create order (first save only creates PK; totals computed after items)
    co = CommerceOrder.objects.create(
        owner=owner,
        party=party,
        order_type="SALE",
        status="pending",
        placed_by="party",
        notes=f"Storefront order: {store_order.order_number}",
        order_source="Online Store",
        discount_type="none",
        discount_value=_safe_decimal(getattr(store_order, "discount_amount", None) or "0"),
        tax_percent=Decimal("0.00"),
    )

    # Items: use raw_name for now (commerce.Product is different from products.Product).
    items = list(store_order.items.select_related("product").all())
    for it in items:
        CommerceOrderItem.objects.create(
            order=co,
            product=None,
            raw_name=(getattr(getattr(it, "product", None), "name", None) or "Item")[:200],
            qty=int(it.qty or 0),
            price=_safe_decimal(getattr(it, "unit_price", None) or "0"),
            tax_percent=Decimal("0.00"),
            warehouse=None,
        )

    # Second save computes totals
    co.save()

    store_order.commerce_order = co
    store_order.save(update_fields=["commerce_order"])
    return co

