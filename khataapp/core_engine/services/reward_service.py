from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from khataapp.core_engine.models.logs import EngineEventLog, RewardLedgerEntry
from khataapp.core_engine.services.admin_control import get_engine_flags
from khataapp.core_engine.services.plan_access import can_access_feature
from khataapp.core_engine.utils.engine import get_or_create_engine_for_update


def _quantize_money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def _money_to_coins(amount: Decimal) -> int:
    # 1 coin per ₹1 (floor).
    if amount <= 0:
        return 0
    return int(amount.quantize(Decimal("1"), rounding=ROUND_DOWN))


def _recompute_level(total_rewards: int) -> int:
    # Simple, deterministic leveling.
    return max(1, 1 + int(total_rewards // 1000))


@transaction.atomic
def add_rewards(
    *,
    owner,
    coins_delta: int = 0,
    points_delta: int = 0,
    source: str,
    amount_reference=Decimal("0.00"),
    related_obj=None,
    meta: Optional[dict] = None,
    actor=None,
) -> RewardLedgerEntry | None:
    """
    Create a RewardLedgerEntry and update cached totals on BusinessGrowthEngine.
    """
    if not owner or not getattr(owner, "is_authenticated", False):
        return None

    if not can_access_feature(owner, "engine.rewards").allowed:
        return None

    flags = get_engine_flags()
    if not flags.enable_rewards:
        return None

    engine = get_or_create_engine_for_update(owner)

    entry = RewardLedgerEntry.objects.create(
        owner=owner,
        source=source,
        coins_delta=int(coins_delta or 0),
        points_delta=int(points_delta or 0),
        amount_reference=_quantize_money(amount_reference),
        meta=meta or {},
        content_type=ContentType.objects.get_for_model(related_obj) if related_obj else None,
        object_id=str(getattr(related_obj, "pk", "")) if related_obj else "",
    )

    engine.total_rewards = max(0, int(engine.total_rewards) + int(entry.coins_delta))
    engine.reward_points = max(0, int(engine.reward_points) + int(entry.points_delta))
    engine.level = _recompute_level(engine.total_rewards)
    engine.last_reward_update = timezone.now()
    engine.admin_profit_formula = flags.profit_formula
    engine.save(
        update_fields=[
            "total_rewards",
            "reward_points",
            "level",
            "last_reward_update",
            "admin_profit_formula",
            "updated_at",
        ]
    )

    EngineEventLog.objects.create(
        owner=owner,
        actor=actor,
        category=EngineEventLog.Category.FLOW,
        level=EngineEventLog.Level.INFO,
        event_key="rewards.add",
        message=f"Rewards updated (+{entry.coins_delta} coins, +{entry.points_delta} points).",
        meta={"source": source, "amount_reference": str(entry.amount_reference), **(meta or {})},
        content_type=entry.content_type,
        object_id=entry.object_id,
    )
    return entry


def award_invoice_rewards(*, invoice, actor=None) -> None:
    """
    Reward on invoice creation: coins derived from invoice amount + GST bonus points.
    """
    if not invoice:
        return
    owner = getattr(getattr(invoice, "order", None), "owner", None)
    if not owner:
        return

    flags = get_engine_flags()
    amount = _quantize_money(getattr(invoice, "amount", 0))
    nominal = (amount * (flags.invoice_reward_percent / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    coins = _money_to_coins(nominal)

    gst_type = (getattr(invoice, "gst_type", "") or "").upper()
    bonus_points = flags.gst_invoice_bonus_points if gst_type == "GST" else flags.nongst_invoice_bonus_points

    add_rewards(
        owner=owner,
        coins_delta=coins,
        points_delta=int(bonus_points or 0),
        source=RewardLedgerEntry.Source.INVOICE,
        amount_reference=amount,
        related_obj=invoice,
        meta={"gst_type": gst_type},
        actor=actor,
    )


def award_payment_rewards(*, payment, actor=None) -> None:
    """
    Reward small points for receiving a payment (habit loop).
    """
    if not payment:
        return
    invoice = getattr(payment, "invoice", None)
    owner = getattr(getattr(invoice, "order", None), "owner", None)
    if not owner:
        return

    amount = _quantize_money(getattr(payment, "amount", 0))
    points = 2 if amount > 0 else 0
    add_rewards(
        owner=owner,
        coins_delta=0,
        points_delta=points,
        source=RewardLedgerEntry.Source.PAYMENT,
        amount_reference=amount,
        related_obj=payment,
        meta={"invoice_id": getattr(invoice, "id", None)},
        actor=actor,
    )

