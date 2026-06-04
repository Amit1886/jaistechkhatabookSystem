from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from commerce.models import Order
from smart_bi.models import FestivalCampaign


def get_active_campaign(owner, *, day=None) -> FestivalCampaign | None:
    if not owner:
        return None
    day = day or timezone.localdate()
    return (
        FestivalCampaign.objects.filter(
            owner=owner,
            status=FestivalCampaign.Status.ACTIVE,
            start_date__lte=day,
            end_date__gte=day,
        )
        .order_by("-start_date", "-id")
        .first()
    )


def _applicable_amount(order: Order, campaign: FestivalCampaign) -> Decimal:
    """
    Sum of line totals eligible for festival discount.

    If campaign has no products selected, treat as "all products".
    """
    items = list(order.items.all().select_related("product"))
    if not items:
        return Decimal("0.00")

    product_ids = set(campaign.products.values_list("id", flat=True))
    has_filter = bool(product_ids)

    total = Decimal("0.00")
    for it in items:
        if not getattr(it, "product_id", None):
            continue
        if has_filter and int(it.product_id) not in product_ids:
            continue
        try:
            qty = Decimal(str(getattr(it, "qty", 0) or 0))
            price = Decimal(str(getattr(it, "price", 0) or 0))
        except Exception:
            continue
        if qty <= 0 or price < 0:
            continue
        total += (qty * price)

    return total.quantize(Decimal("0.01"))


@transaction.atomic
def apply_festival_discount(order: Order, *, day=None, save: bool = True) -> Decimal:
    """
    Apply the active festival campaign (if any) to the given order.

    Rules:
    - Applies only for SALE orders.
    - Applies only once; if the order already has a festival_campaign, it is not overwritten.
    """
    if not order or not getattr(order, "owner", None):
        return Decimal("0.00")

    if (getattr(order, "order_type", "") or "").upper() != "SALE":
        return Decimal("0.00")

    if getattr(order, "festival_campaign_id", None):
        try:
            return Decimal(str(getattr(order, "festival_discount_amount", 0) or 0)).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    campaign = get_active_campaign(order.owner, day=day)
    if not campaign:
        return Decimal("0.00")

    eligible = _applicable_amount(order, campaign)
    if eligible <= 0:
        return Decimal("0.00")

    discount = campaign.discount_amount_for(eligible)
    if discount < 0:
        discount = Decimal("0.00")
    if discount > eligible:
        discount = eligible
    discount = discount.quantize(Decimal("0.01"))

    order.festival_campaign = campaign
    order.festival_discount_amount = discount
    if save:
        order.save()
    return discount


def suggested_campaigns_for(day=None) -> list[dict]:
    """
    Simple calendar-based suggestions (heuristic).
    """
    day = day or timezone.localdate()
    m = int(day.month)

    suggestions: list[dict] = []
    if m in {10, 11}:
        suggestions.append({"name": "Diwali Sale", "theme": "diwali", "discount_type": "percentage", "discount_value": "10.00"})
    if m == 3:
        suggestions.append({"name": "Holi Discount", "theme": "holi", "discount_type": "percentage", "discount_value": "12.00"})
    if m in {12, 1}:
        suggestions.append({"name": "New Year Offer", "theme": "new_year", "discount_type": "percentage", "discount_value": "8.00"})

    return suggestions

