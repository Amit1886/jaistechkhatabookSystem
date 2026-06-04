from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from event_bus.kafka_client import is_kafka_enabled, send_kafka_message
from event_bus.models import EventOutbox

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def flush_outbox(self, limit: int = 200) -> dict:
    """
    Flush pending outbox events to Kafka (or future backends).
    """
    if not is_kafka_enabled():
        return {"ok": True, "flushed": 0, "skipped": True, "reason": "kafka_disabled"}

    limit = max(10, min(int(limit or 200), 1000))
    qs = EventOutbox.objects.filter(status=EventOutbox.Status.PENDING).order_by("created_at")[:limit]
    rows = list(qs)
    if not rows:
        return {"ok": True, "flushed": 0}

    flushed = 0
    failed = 0
    kept_pending = 0
    for ev in rows:
        ok, err = send_kafka_message(topic=ev.topic, key=ev.key or "", payload={"type": ev.event_type, "payload": ev.payload, "id": str(ev.id)})
        with transaction.atomic():
            ev.attempts = int(ev.attempts or 0) + 1
            if ok:
                ev.status = EventOutbox.Status.SENT
                ev.sent_at = timezone.now()
                ev.last_error = ""
                flushed += 1
            else:
                # Keep pending for transient failures; mark FAILED only after several attempts.
                ev.last_error = (err or "")[:2000]
                if ev.attempts >= 5:
                    ev.status = EventOutbox.Status.FAILED
                    failed += 1
                else:
                    ev.status = EventOutbox.Status.PENDING
                    kept_pending += 1
            ev.save(update_fields=["status", "attempts", "sent_at", "last_error", "updated_at"])

    return {"ok": True, "flushed": flushed, "failed": failed, "pending": kept_pending}
