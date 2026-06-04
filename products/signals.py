from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import Product


@receiver(post_save, sender=Product)
def sync_product_to_storefront(sender, instance: Product, created: bool, **kwargs):
    """
    Product Auto Sync (critical):
    - When a billing Product is created/updated, ensure vendor listings exist for vendors
      that have this product in any of their linked warehouses.
    - Keep listing online flag in sync with Product.is_online.
    """
    try:
        from vendors.models import VendorWarehouse
        from storefront.models import VendorProductListing

        vendor_ids = list(
            VendorWarehouse.objects.filter(is_active=True, warehouse__inventories__product=instance)
            .values_list("vendor_id", flat=True)
            .distinct()
        )
        for vendor_id in vendor_ids:
            listing, _ = VendorProductListing.objects.get_or_create(vendor_id=vendor_id, product=instance)
            if listing.is_online != instance.is_online:
                listing.is_online = instance.is_online
                listing.save(update_fields=["is_online", "updated_at"])
    except Exception:
        # Keep billing stable even if storefront tables are not migrated yet.
        return

