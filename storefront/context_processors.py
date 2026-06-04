from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict

from django.core.cache import cache
from django.urls import reverse

from products.models import Category
from vendors.models import Vendor, VendorMembership

from .models import VendorProductListing


def storefront_nav(request) -> Dict[str, Any]:
    """
    Lightweight storefront navigation context for mega-menu UI.

    Only activates on `/store/<subdomain>/...` routes where `subdomain` is present
    in the resolved URL kwargs.
    """
    try:
        subdomain = (getattr(getattr(request, "resolver_match", None), "kwargs", {}) or {}).get("subdomain")
    except Exception:
        subdomain = None
    subdomain = (subdomain or "").strip().lower()
    if not subdomain:
        return {}

    vendor = Vendor.objects.filter(subdomain=subdomain, is_active=True).only("id", "subdomain").first()
    if not vendor:
        return {}

    cache_key = f"storefront:nav:{vendor.id}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    # Categories present in online listings (keep stable ordering).
    categories = list(
        Category.objects.filter(products__vendor_listings__vendor=vendor, products__vendor_listings__is_online=True)
        .distinct()
        .order_by("name")
        .only("id", "name", "slug")
    )

    # Build "sub-links" using top products per category (as a Meesho-like dropdown).
    # Avoid N+1: fetch a limited set and group in python.
    listings = (
        VendorProductListing.objects.select_related("product", "product__category")
        .filter(vendor=vendor, is_online=True, product__category__isnull=False)
        .order_by("-is_featured", "-updated_at")[:80]
    )
    per_cat: Dict[int, list[dict]] = defaultdict(list)
    for l in listings:
        cat = getattr(getattr(l, "product", None), "category", None)
        if not cat:
            continue
        if len(per_cat[cat.id]) >= 8:
            continue
        per_cat[cat.id].append({"name": l.effective_title, "slug": l.product.slug})

    popular = []
    for l in listings[:10]:
        try:
            popular.append({"name": l.effective_title, "slug": l.product.slug})
        except Exception:
            continue

    # Delivery location stored in session (per vendor).
    try:
        delivery = (request.session.get("store_delivery") or {}).get(str(vendor.id)) or {}
    except Exception:
        delivery = {}
    delivery_label = str(delivery.get("label") or "").strip()
    if not delivery_label:
        p = str(delivery.get("pincode") or "").strip()
        delivery_label = p or ""

    ctx = {
        "store_nav_vendor_id": vendor.id,
        "store_nav_categories": categories,
        "store_nav_columns": [{"category": c, "links": per_cat.get(c.id, [])} for c in categories],
        "store_nav_popular": popular,
        "store_delivery_location": {
            "label": delivery_label,
            "pincode": str(delivery.get("pincode") or "").strip(),
            "latitude": delivery.get("latitude"),
            "longitude": delivery.get("longitude"),
        },
    }
    cache.set(cache_key, ctx, timeout=60)
    return ctx


def user_vendor_switch(request) -> Dict[str, Any]:
    """
    Global context: provide a switch target to the vendor dashboard for the logged-in user.

    Used to show "Billing <-> E-commerce" links across both UIs using the same login.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    vendor = None
    try:
        vendor = user.vendor
    except Exception:
        vendor = None

    if not vendor:
        vendor = (
            VendorMembership.objects.select_related("vendor")
            .filter(user=user, is_active=True, vendor__is_active=True)
            .order_by("-role", "-id")
            .values("vendor__id", "vendor__name", "vendor__subdomain")
            .first()
        )
        if vendor:
            return {
                "switch_vendor": {
                    "id": vendor["vendor__id"],
                    "name": vendor["vendor__name"],
                    "subdomain": vendor["vendor__subdomain"],
                },
                "switch_vendor_dashboard_url": reverse("vendor-dashboard-ui", args=[vendor["vendor__subdomain"]]),
                "switch_store_url": reverse("store-home", args=[vendor["vendor__subdomain"]]),
            }
        return {}

    try:
        sub = vendor.subdomain
        name = vendor.name
        vid = vendor.id
    except Exception:
        return {}

    return {
        "switch_vendor": {"id": vid, "name": name, "subdomain": sub},
        "switch_vendor_dashboard_url": reverse("vendor-dashboard-ui", args=[sub]),
        "switch_store_url": reverse("store-home", args=[sub]),
    }


def storefront_apps(request) -> Dict[str, Any]:
    """
    Storefront app marketplace runtime injection.

    Only activates on `/store/<subdomain>/...` routes.
    """

    try:
        subdomain = (getattr(getattr(request, "resolver_match", None), "kwargs", {}) or {}).get("subdomain")
    except Exception:
        subdomain = None
    subdomain = (subdomain or "").strip().lower()
    if not subdomain:
        return {}

    vendor = Vendor.objects.filter(subdomain=subdomain, is_active=True).only("id", "subdomain", "name", "owner_id").first()
    if not vendor:
        return {}

    try:
        from vendors.services.marketplace_apps import enabled_apps_for_storefront

        apps = enabled_apps_for_storefront(vendor)
    except Exception:
        apps = {}

    return {"storefront_apps": apps}
