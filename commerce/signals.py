from django.db.models.signals import post_save
from django.dispatch import receiver

from event_bus.publish import publish_event
from ledger.utils import add_invoice_to_ledger

from .models import Invoice

@receiver(post_save, sender=Invoice)
def create_invoice_ledger(sender, instance, created, **kwargs):
    if created:
        add_invoice_to_ledger(instance)
        try:
            from smart_bi.services.fraud_detection import detect_invoice_anomaly

            detect_invoice_anomaly(invoice=instance)
        except Exception:
            pass
        try:
            try:
                from realtime.services.publisher import publish_event as publish_realtime

                owner = getattr(getattr(instance, "order", None), "owner", None)
                if owner:
                    publish_realtime(f"owner_{owner.id}", "invoice.created", {"invoice_id": instance.id, "amount": str(instance.amount), "number": instance.number})
            except Exception:
                pass

            publish_event(
                topic="billing.events",
                event_type="invoice.created",
                owner=getattr(getattr(instance, "order", None), "owner", None),
                key=str(getattr(instance, "number", "") or getattr(instance, "id", "")),
                payload={
                    "invoice_id": getattr(instance, "id", None),
                    "invoice_number": getattr(instance, "number", ""),
                    "amount": str(getattr(instance, "amount", "")),
                    "status": getattr(instance, "status", ""),
                },
            )
        except Exception:
            pass
