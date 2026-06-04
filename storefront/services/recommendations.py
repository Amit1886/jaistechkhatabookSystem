from __future__ import annotations

from django.db.models import Count

from ..models import StoreOrderItem, VendorProductListing


def recommend_for_listing(*, listing: VendorProductListing, limit: int = 12):
    vendor = listing.vendor
    product = listing.product

    same_cat_qs = (
        VendorProductListing.objects.select_related("product", "product__category")
        .filter(vendor=vendor, is_online=True, product__category=product.category)
        .exclude(id=listing.id)
        .order_by("-is_featured", "-updated_at")
    )
    candidates = list(same_cat_qs[:limit])
    if len(candidates) >= limit:
        return candidates

    order_ids = (
        StoreOrderItem.objects.filter(product=product)
        .values_list("order_id", flat=True)
        .distinct()[:500]
    )
    other_items = StoreOrderItem.objects.filter(order_id__in=order_ids).exclude(product=product)
    counts = other_items.values("product_id").annotate(c=Count("id")).order_by("-c")[:200]
    product_ids = [row["product_id"] for row in counts]
    if not product_ids:
        return candidates

    listing_map = {
        l.product_id: l
        for l in VendorProductListing.objects.filter(vendor=vendor, is_online=True, product_id__in=product_ids)
    }
    ordered = []
    for pid in product_ids:
        l = listing_map.get(pid)
        if l and l.id != listing.id:
            ordered.append(l)
        if len(candidates) + len(ordered) >= limit:
            break
    return candidates + ordered[: max(0, limit - len(candidates))]

