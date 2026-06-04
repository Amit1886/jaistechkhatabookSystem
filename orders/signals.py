from django.db.models.signals import post_save
from django.dispatch import receiver

from realtime.services.publisher import publish_event
from orders.models import Order


@receiver(post_save, sender=Order)
def publish_order_events(sender, instance: Order, created: bool, **kwargs):
    payload = {
        "id": instance.id,
        "order_number": instance.order_number,
        "status": instance.status,
        "order_type": instance.order_type,
        "customer": instance.customer_id,
        "salesman": instance.salesman_id,
        "warehouse": instance.warehouse_id,
        "total_amount": float(instance.total_amount or 0),
        "margin_amount": float(instance.margin_amount or 0),
        "created_at": instance.created_at.isoformat(),
    }
    event_type = "order.created" if created else "order.updated"
    publish_event("sales_live", event_type, payload)
