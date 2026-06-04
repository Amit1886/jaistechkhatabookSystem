from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomerProfile, StoreOrder
from .models import VendorProductListing


@receiver(post_save, sender=StoreOrder)
def ensure_order_customer_profile(sender, instance: StoreOrder, created: bool, **kwargs):
    if not created:
        return
    try:
        CustomerProfile.objects.get_or_create(user=instance.customer)
    except Exception:
        pass
    try:
        # Lazy import to avoid pulling WhatsApp providers during migrations/app loading.
        from .services.whatsapp_notifications import notify_order_placed

        notify_order_placed(order=instance)
    except Exception:
        pass


@receiver(post_save, sender=StoreOrder)
def auto_settle_on_paid(sender, instance: StoreOrder, created: bool, **kwargs):
    if instance.payment_status != StoreOrder.PaymentStatus.PAID:
        return
    try:
        # Lazy import to keep app-load light and avoid circular dependencies.
        from .services.settlements import settle_paid_order

        settle_paid_order(order=instance)
    except Exception:
        pass


@receiver(post_save, sender="products.WarehouseInventory")
def ensure_vendor_listing_on_inventory(sender, instance, created: bool, **kwargs):
    """
    When a product is added to a warehouse (billing/ERP inventory), ensure it appears
    in the vendor dashboard as a draft listing that can be edited/published.

    This does NOT auto-publish to the store; vendor controls `is_online`.
    """
    try:
        warehouse_id = getattr(instance, "warehouse_id", None)
        product_id = getattr(instance, "product_id", None)
        if not warehouse_id or not product_id:
            return
    except Exception:
        return

    try:
        from django.db.models import Q

        from vendors.models import Vendor

        vendor_qs = Vendor.objects.filter(is_active=True).filter(
            Q(primary_warehouse_id=warehouse_id) | Q(warehouses__id=warehouse_id)
        )
        vendor_qs = vendor_qs.distinct().only("id")
        vendor_ids = list(vendor_qs.values_list("id", flat=True)[:50])
    except Exception:
        vendor_ids = []

    if not vendor_ids:
        return

    for vid in vendor_ids:
        try:
            VendorProductListing.objects.get_or_create(
                vendor_id=vid,
                product_id=product_id,
                defaults={"is_online": False},
            )
        except Exception:
            continue


@receiver(post_save, sender="commerce.Product")
def sync_commerce_product_to_storefront(sender, instance, created: bool, **kwargs):
    """
    Bridge billing `commerce.Product` to storefront `products.Product` so the ecommerce
    store uses the same catalog and inventory, without breaking existing billing logic.

    - Uses `sku` as the stable mapping key.
    - Creates/updates `products.Product` and `products.WarehouseInventory` for the vendor's primary warehouse.
    - Vendor sees draft listing in vendor dashboard and can publish (`is_online` on listing).
    """
    try:
        from .services.commerce_product_sync import sync_commerce_product_to_storefront

        sync_commerce_product_to_storefront(commerce_product=instance)
    except Exception:
        return
