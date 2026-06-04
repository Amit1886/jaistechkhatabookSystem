from __future__ import annotations

from django.utils import timezone

from storefront.models import VendorProductListing


SESSION_KEY = "storefront_wishlist_v1"


def _get_root(session) -> dict:
    root = session.get(SESSION_KEY)
    if not isinstance(root, dict):
        root = {}
        session[SESSION_KEY] = root
    return root


def get_vendor_wishlist_ids(session, vendor_id: int) -> set[int]:
    root = _get_root(session)
    vendor_key = str(int(vendor_id))
    ids = root.get(vendor_key)
    if not isinstance(ids, list):
        ids = []
        root[vendor_key] = ids
        session[SESSION_KEY] = root
    out: set[int] = set()
    for v in ids:
        try:
            out.add(int(v))
        except Exception:
            continue
    return out


def toggle(session, *, vendor_id: int, listing_id: int) -> bool:
    root = _get_root(session)
    vendor_key = str(int(vendor_id))
    ids = root.get(vendor_key)
    if not isinstance(ids, list):
        ids = []
    sid = int(listing_id)
    if sid in [int(x) for x in ids if str(x).isdigit()]:
        ids = [x for x in ids if int(x) != sid]
        root[vendor_key] = ids
        session[SESSION_KEY] = root
        session.modified = True
        return False
    ids.append(sid)
    root[vendor_key] = ids
    root["_updated_at"] = timezone.now().isoformat()
    session[SESSION_KEY] = root
    session.modified = True
    return True


def build_wishlist_view(*, vendor, session) -> dict:
    ids = list(get_vendor_wishlist_ids(session, vendor.id))
    listings = list(
        VendorProductListing.objects.select_related("product", "product__category")
        .filter(vendor=vendor, is_online=True, id__in=ids)
        .order_by("-updated_at")[:200]
    )
    listing_ids = {l.id for l in listings}
    return {"listings": listings, "count": len(ids), "ids": listing_ids}

