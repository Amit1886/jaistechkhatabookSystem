from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from vendors.models import Vendor

from .models import StoreShipment


@shared_task
def poll_shiprocket_tracking(limit: int = 200):
    """
    Poll Shiprocket tracking as a fallback when webhooks are delayed.
    Safe to run periodically (e.g., every 30-60 minutes).
    """
    qs = (
        StoreShipment.objects.select_related("order", "order__vendor")
        .filter(provider="shiprocket")
        .exclude(status__in=["delivered", "failed"])
        .exclude(tracking_number="")
        .order_by("last_tracked_at", "updated_at")[: max(1, int(limit or 200))]
    )
    from storefront.services.shipping.provider import track_shipment

    now = timezone.now()
    for shipment in qs:
        vendor: Vendor = shipment.order.vendor
        cfg = vendor.shipping_providers.filter(provider="shiprocket", is_active=True).first()
        if not cfg:
            continue
        # Avoid hammering the provider for the same shipment.
        if shipment.last_tracked_at and shipment.last_tracked_at > now - timedelta(minutes=20):
            continue
        live = track_shipment(provider="shiprocket", config=(cfg.config or {}), tracking_number=shipment.tracking_number)
        shipment.payload = {**(shipment.payload or {}), **{"poll_track": live}}
        shipment.last_tracked_at = now
        shipment.save(update_fields=["payload", "last_tracked_at", "updated_at"])

