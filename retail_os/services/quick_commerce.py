from decimal import Decimal

from django.db.models import F
from django.utils import timezone

from ..models import DeliveryAllocation, PackingTask, QuickCommerceOrder, RiderProfile
from .realtime import publish_retail_event


def create_packing_tasks(quick_order):
    tasks = []
    for item in quick_order.order.items.select_related("product"):
        tasks.append(PackingTask.objects.create(quick_order=quick_order, product=item.product, qty=item.qty))
    publish_retail_event("quick_commerce", "packing.queue.updated", {"quick_order_id": quick_order.id, "tasks": len(tasks)})
    return tasks


def allocate_nearest_rider(quick_order):
    rider = (
        RiderProfile.objects.filter(branch=quick_order.branch, is_available=True)
        .order_by("active_order_count", "-rating", "-last_seen_at")
        .first()
    )
    allocation, _ = DeliveryAllocation.objects.update_or_create(
        quick_order=quick_order,
        defaults={
            "rider": rider,
            "allocation_score": Decimal("100.00") if rider else Decimal("0.00"),
            "eta_minutes": quick_order.promised_eta_minutes,
            "status": "allocated" if rider else "waiting_for_rider",
        },
    )
    if rider:
        RiderProfile.objects.filter(pk=rider.pk).update(active_order_count=F("active_order_count") + 1)
        quick_order.status = QuickCommerceOrder.Status.RIDER_ASSIGNED
        quick_order.save(update_fields=["status", "updated_at"])
    publish_retail_event(
        "quick_commerce",
        "rider.allocated",
        {"quick_order_id": quick_order.id, "rider_id": rider.id if rider else None, "status": allocation.status},
    )
    return allocation


def mark_order_packed(quick_order):
    quick_order.status = QuickCommerceOrder.Status.PACKED
    quick_order.packed_at = timezone.now()
    quick_order.save(update_fields=["status", "packed_at", "updated_at"])
    publish_retail_event("quick_commerce", "order.packed", {"quick_order_id": quick_order.id})
    return quick_order

