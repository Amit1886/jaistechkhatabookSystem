from django.db import transaction

from apps.platform.core.application.services.event_service import EventService
from apps.platform.core.models import StockLedgerEntry


class InventoryService:
    def __init__(self, event_service=None):
        self.event_service = event_service or EventService()

    @transaction.atomic
    def post_stock_movement(
        self,
        *,
        tenant,
        warehouse,
        product,
        quantity,
        movement_type,
        variant=None,
        unit_cost=0,
        reference_type="",
        reference_id="",
        **extra,
    ):
        entry = StockLedgerEntry.objects.create(
            tenant=tenant,
            warehouse=warehouse,
            product=product,
            variant=variant,
            quantity=quantity,
            movement_type=movement_type,
            unit_cost=unit_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            batch_no=extra.get("batch_no", ""),
            serial_no=extra.get("serial_no", ""),
            expiry_date=extra.get("expiry_date"),
            metadata=extra.get("metadata", {}),
        )
        self.event_service.publish(
            "stock_updated",
            {
                "entry_id": str(entry.id),
                "product_id": str(product.id),
                "warehouse_id": str(warehouse.id),
                "quantity": str(quantity),
                "movement_type": movement_type,
            },
            tenant=tenant,
        )
        return entry

