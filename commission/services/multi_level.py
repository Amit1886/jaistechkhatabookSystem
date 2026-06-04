from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction

from commission.models import CommissionScheme
from users.models import CommissionLedger
from wallet.services import credit

User = get_user_model()


def _role(user: User) -> str:
    return (getattr(user, "role", "") or "").strip().lower()


def _upline(user: User, max_depth: int = 5) -> Iterable[User]:
    current = getattr(user, "parent", None)
    depth = 0
    while current and depth < max_depth:
        yield current
        current = getattr(current, "parent", None)
        depth += 1


@transaction.atomic
def distribute(event_type: str, *, amount: Decimal, actor: User, metadata=None):
    """
    Multi-level commission distribution.

    - Traverse parent chain up to 5 levels.
    - For each role, look up CommissionScheme(event_type, role).
    - Record in CommissionLedger and credit wallet.
    """

    if amount <= 0:
        return []

    results = []
    chain = [actor] + list(_upline(actor))
    metadata = metadata or {}

    for user in chain:
        role = _role(user)
        scheme = CommissionScheme.objects.filter(event_type=event_type, role=role, is_active=True).first()
        if not scheme or scheme.percent <= 0:
            continue
        commission_amount = (amount * scheme.percent) / Decimal("100.00")
        if commission_amount <= 0:
            continue
        CommissionLedger.objects.create(
            user=user,
            order_id=str(metadata.get("source_id", ""))[:50],
            role=role,
            margin=amount,
            commission_amount=commission_amount,
            metadata={"event_type": event_type, **metadata},
        )
        credit(user, commission_amount, source=f"commission.{event_type}", reference=str(metadata.get("source_id", "")))
        results.append({"user_id": user.id, "role": role, "amount": commission_amount})
    return results

