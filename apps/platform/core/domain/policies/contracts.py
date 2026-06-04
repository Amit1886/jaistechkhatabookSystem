from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""
    effects: dict[str, Any] = field(default_factory=dict)

