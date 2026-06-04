from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from superapp.models import KitchenQueue, OrderStatusLog, TableOrder


def calculate_order_totals(items):
    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")
    for item in items or []:
        qty = Decimal(str(item.get("quantity") or 1))
        price = Decimal(str(item.get("price") or 0))
        rate = Decimal(str(item.get("tax_rate") or 0))
        line = qty * price
        subtotal += line
        tax_amount += (line * rate / Decimal("100")).quantize(Decimal("0.01"))
    return subtotal.quantize(Decimal("0.01")), tax_amount.quantize(Decimal("0.01"))


@transaction.atomic
def create_table_order(*, table=None, customer=None, items=None, notes=""):
    subtotal, tax_amount = calculate_order_totals(items)
    order = TableOrder.objects.create(
        table=table,
        customer=customer,
        order_number=f"TBL-{timezone.now():%Y%m%d%H%M%S%f}",
        items=items or [],
        notes=notes,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=subtotal + tax_amount,
    )
    KitchenQueue.objects.create(order=order)
    OrderStatusLog.objects.create(order=order, new_status=order.status, actor=customer, note="Order placed")
    if table:
        table.status = "occupied"
        table.save(update_fields=["status", "updated_at"])
    return order


@transaction.atomic
def update_order_status(order: TableOrder, status: str, *, actor=None, note: str = ""):
    previous = order.status
    order.status = status
    order.save(update_fields=["status", "updated_at"])
    OrderStatusLog.objects.create(order=order, previous_status=previous, new_status=status, actor=actor, note=note)
    if hasattr(order, "kitchen_queue"):
        queue = order.kitchen_queue
        queue.status = status
        if status == "preparing" and not queue.cooking_started_at:
            queue.cooking_started_at = timezone.now()
        if status == "ready":
            queue.ready_at = timezone.now()
        queue.save()
    return order

