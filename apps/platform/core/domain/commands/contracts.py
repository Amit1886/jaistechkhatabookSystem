from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Command:
    command_type: str
    payload: dict[str, Any]
    tenant_id: str | None = None
    actor_id: str | None = None
    idempotency_key: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

