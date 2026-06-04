from __future__ import annotations

from decimal import Decimal

from django.db.models import QuerySet

from storefront.models import VendorProductListing
from vendors.models import Vendor, VendorCatalog, VendorCatalogProduct, VendorStoreSettings


def get_default_catalog_id(vendor: Vendor) -> int | None:
    try:
        settings_obj = getattr(vendor, "store_settings", None)
        if not settings_obj:
            settings_obj = VendorStoreSettings.objects.filter(vendor=vendor).first()
        blob = (settings_obj.settings_json or {}) if settings_obj else {}
        cid = blob.get("default_catalog_id")
        if cid:
            return int(cid)
    except Exception:
        return None
    return None


def set_default_catalog(vendor: Vendor, catalog: VendorCatalog | None):
    settings_obj, _ = VendorStoreSettings.objects.get_or_create(vendor=vendor)
    blob = dict(settings_obj.settings_json or {})
    blob["default_catalog_id"] = int(catalog.id) if catalog else None
    settings_obj.settings_json = blob
    settings_obj.save(update_fields=["settings_json", "updated_at"])


def resolve_active_catalog(*, vendor: Vendor, catalog_id: str | None = None) -> VendorCatalog | None:
    cid = None
    try:
        if catalog_id:
            cid = int(str(catalog_id).strip())
    except Exception:
        cid = None

    qs = VendorCatalog.objects.filter(vendor=vendor, is_active=True).order_by("-updated_at", "-id")
    if cid:
        return qs.filter(id=cid).first()

    default_id = get_default_catalog_id(vendor)
    if default_id:
        c = qs.filter(id=default_id).first()
        if c:
            return c

    return qs.first()


def apply_catalog_filter(qs: QuerySet[VendorProductListing], *, catalog: VendorCatalog | None) -> QuerySet[VendorProductListing]:
    if not catalog:
        return qs

    items = VendorCatalogProduct.objects.filter(catalog=catalog)
    excluded_ids = items.filter(mode=VendorCatalogProduct.Mode.EXCLUDE).values_list("listing_id", flat=True)
    if catalog.auto_include_new_products:
        return qs.exclude(id__in=excluded_ids)

    included_ids = items.filter(mode=VendorCatalogProduct.Mode.INCLUDE).values_list("listing_id", flat=True)
    return qs.filter(id__in=included_ids).exclude(id__in=excluded_ids)


def apply_price_adjustment(*, price: Decimal, catalog: VendorCatalog | None) -> Decimal:
    if not catalog:
        return price
    try:
        pct = Decimal(str(catalog.price_adjustment_percent or 0))
        if pct <= 0:
            return price
        factor = (pct / Decimal("100"))
        if catalog.price_adjustment_direction == VendorCatalog.PriceDirection.INCREASE:
            out = price * (Decimal("1.0") + factor)
        else:
            out = price * (Decimal("1.0") - factor)
        if out < 0:
            out = Decimal("0.00")
        return out.quantize(Decimal("0.01"))
    except Exception:
        return price

