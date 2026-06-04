from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Query:
    query_key: str
    filters: dict[str, Any] = field(default_factory=dict)
    tenant_id: str | None = None
    actor_id: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

