from __future__ import annotations

from decimal import Decimal

from django.utils.text import slugify


def sync_commerce_product_to_storefront(*, commerce_product) -> None:
    """
    Bridge billing `commerce.Product` -> storefront `products.Product` + `products.WarehouseInventory`
    + vendor draft listing, plus media sync (single image).

    Safe to call from signals or from bulk import flows.
    """

    owner_id = getattr(commerce_product, "owner_id", None)
    sku = (getattr(commerce_product, "sku", None) or "").strip()
    if not owner_id or not sku:
        return

    from products.models import Category as CatalogCategory
    from products.models import Product as CatalogProduct
    from products.models import ProductMedia, WarehouseInventory
    from vendors.models import Vendor
    from storefront.models import VendorProductListing

    vendor = Vendor.objects.filter(owner_id=owner_id, is_active=True).only("id", "primary_warehouse_id").first()
    if not vendor or not vendor.primary_warehouse_id:
        return

    # Category mapping (per-owner commerce.Category -> global products.Category)
    cat_obj = None
    try:
        cat_name = (getattr(getattr(commerce_product, "category", None), "name", None) or "").strip()
        if cat_name:
            cat_slug = slugify(f"{cat_name}-{owner_id}")[:120]
            cat_obj, _ = CatalogCategory.objects.get_or_create(slug=cat_slug, defaults={"name": cat_name})
    except Exception:
        cat_obj = None

    barcode = f"SYNC-{sku}"[:128]
    price = Decimal(str(getattr(commerce_product, "price", 0) or 0))

    defaults = {
        "name": (getattr(commerce_product, "name", "") or "").strip()[:200] or sku,
        "category": cat_obj,
        "gst_percent": getattr(commerce_product, "gst_rate", 0) or 0,
        "mrp": price,
        "b2b_price": price,
        "b2c_price": price,
        "wholesale_price": price,
        "description": (getattr(commerce_product, "description", "") or "").strip(),
        "hs_code": (getattr(commerce_product, "hsn_code", "") or "").strip()[:32],
        "is_active": True,
        "is_online": True if getattr(commerce_product, "stock", 0) is not None else False,
        "track_inventory": True,
    }

    catalog_product = CatalogProduct.objects.filter(sku=sku).first()
    if catalog_product:
        CatalogProduct.objects.filter(id=catalog_product.id).update(**defaults)
        catalog_product.refresh_from_db()
    else:
        catalog_product = CatalogProduct.objects.create(**({"sku": sku, "barcode": barcode, **defaults}))

    # Mirror stock.
    try:
        stock_i = int(getattr(commerce_product, "stock", 0) or 0)
    except Exception:
        stock_i = 0

    inv, _ = WarehouseInventory.objects.get_or_create(
        warehouse_id=vendor.primary_warehouse_id,
        product=catalog_product,
        defaults={"available_qty": stock_i, "reserved_qty": 0},
    )
    if inv.available_qty != stock_i:
        inv.available_qty = stock_i
        inv.save(update_fields=["available_qty", "updated_at"])

    # Ensure draft listing.
    VendorProductListing.objects.get_or_create(
        vendor=vendor,
        product=catalog_product,
        defaults={"is_online": False},
    )

    # Sync single commerce image into ProductMedia (image) if present.
    try:
        img = getattr(commerce_product, "image", None)
        if img and hasattr(img, "name") and img.name:
            # Avoid duplicates for same file name.
            exists = ProductMedia.objects.filter(product=catalog_product, media_type="image", media__icontains=img.name).exists()
            if not exists:
                ProductMedia.objects.create(product=catalog_product, media_type="image", media=img, alt_text=catalog_product.name[:200], sort_order=0)
    except Exception:
        pass

