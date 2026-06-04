from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from khataapp.core_engine.models.loyalty import LoyaltyAccount, LoyaltyLedgerEntry
from khataapp.core_engine.models.logs import EngineEventLog
from khataapp.core_engine.services.admin_control import get_engine_flags
from khataapp.core_engine.services.plan_access import can_access_feature
from khataapp.core_engine.utils.engine import get_or_create_engine_for_update


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def _points_for_amount(amount: Decimal) -> int:
    # 1 point per ₹100 of credit volume (floor).
    if amount <= 0:
        return 0
    return int((amount / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_DOWN))


@transaction.atomic
def ensure_loyalty_account(*, owner, party) -> LoyaltyAccount | None:
    if not owner or not party:
        return None
    if not can_access_feature(owner, "engine.loyalty").allowed:
        return None

    acct = LoyaltyAccount.objects.select_for_update().filter(party=party).first()
    if acct:
        return acct
    return LoyaltyAccount.objects.create(owner=owner, party=party)


@transaction.atomic
def add_loyalty(
    *,
    owner,
    party,
    points_delta: int = 0,
    cashback_delta=Decimal("0.00"),
    source: str,
    related_obj=None,
    meta: Optional[dict] = None,
    actor=None,
) -> LoyaltyLedgerEntry | None:
    if not owner or not getattr(owner, "is_authenticated", False):
        return None
    if not can_access_feature(owner, "engine.loyalty").allowed:
        return None

    flags = get_engine_flags()
    if not flags.enable_loyalty:
        return None

    acct = ensure_loyalty_account(owner=owner, party=party)
    if not acct:
        return None

    entry = LoyaltyLedgerEntry.objects.create(
        account=acct,
        owner=owner,
        source=source,
        points_delta=int(points_delta or 0),
        cashback_delta=_q(cashback_delta),
        meta=meta or {},
    )

    acct.points = int(acct.points) + int(entry.points_delta)
    acct.cashback_total = _q(acct.cashback_total) + _q(entry.cashback_delta)
    acct.save(update_fields=["points", "cashback_total", "updated_at"])

    # Cache total loyalty points issued on the engine (for dashboards).
    engine = get_or_create_engine_for_update(owner)
    engine.loyalty_points = max(0, int(engine.loyalty_points) + int(entry.points_delta))
    engine.save(update_fields=["loyalty_points", "updated_at"])

    EngineEventLog.objects.create(
        owner=owner,
        actor=actor,
        category=EngineEventLog.Category.FLOW,
        level=EngineEventLog.Level.INFO,
        event_key="loyalty.add",
        message=f"Loyalty updated (+{entry.points_delta} points).",
        meta={"party_id": getattr(party, "id", None), "source": source, **(meta or {})},
        content_type=ContentType.objects.get_for_model(related_obj) if related_obj else None,
        object_id=str(getattr(related_obj, "pk", "")) if related_obj else "",
    )

    return entry


def award_for_transaction(*, transaction, actor=None) -> None:
    """
    Award loyalty points on credit transactions.
    """
    if not transaction:
        return
    party = getattr(transaction, "party", None)
    owner = getattr(party, "owner", None)
    if not owner:
        return
    if (getattr(transaction, "txn_type", "") or "").lower() != "credit":
        return

    amount = _q(getattr(transaction, "amount", 0))
    points = _points_for_amount(amount)
    if points <= 0:
        return

    add_loyalty(
        owner=owner,
        party=party,
        points_delta=points,
        cashback_delta=Decimal("0.00"),
        source=LoyaltyLedgerEntry.Source.TRANSACTION,
        related_obj=transaction,
        meta={"amount": str(amount)},
        actor=actor,
    )

