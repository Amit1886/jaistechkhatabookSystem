from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import transaction

from event_bus.models import EventOutbox

logger = logging.getLogger(__name__)


def publish_event(
    *,
    topic: str,
    event_type: str,
    payload: dict[str, Any],
    owner=None,
    key: str = "",
) -> EventOutbox:
    """
    Publish a business event using the Outbox pattern (DB first).
    """
    ev = EventOutbox(topic=(topic or "").strip()[:120], event_type=(event_type or "").strip()[:120], payload=payload or {})
    if owner is not None:
        ev.owner = owner
    if key:
        ev.key = str(key)[:120]

    # If inside a DB transaction, ensure outbox is written in the same commit.
    if transaction.get_connection().in_atomic_block:
        ev.save()
    else:
        # Even without an atomic block, save normally.
        ev.save()
    return ev

