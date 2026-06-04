from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    payload: dict[str, Any]
    tenant_id: str | None = None
    actor_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    source: str = "platform.core"


ENTERPRISE_EVENTS = {
    "invoice_created",
    "payment_received",
    "purchase_completed",
    "stock_low",
    "user_logged_in",
    "workflow_approved",
    "workflow_transitioned",
    "stock_updated",
    "journal_posted",
}

