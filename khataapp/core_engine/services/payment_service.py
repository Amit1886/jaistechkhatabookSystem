from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from django.db import transaction

from khataapp.core_engine.models.logs import EngineEventLog
from khataapp.core_engine.services.admin_control import get_engine_flags
from khataapp.core_engine.services.plan_access import can_access_feature
from khataapp.core_engine.utils.engine import get_or_create_engine_for_update
from khataapp.core_engine.utils.profit import apply_profit_protection


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


@transaction.atomic
def record_payment_received(*, payment, actor=None) -> None:
    """
    payment_received -> commission + reward.

    We treat "payment_commission_percent" as a platform fee percent on payment amount.
    User commission is capped by the ProfitProtectionFormula (<=30% of platform fee),
    ensuring the company_share is always >= 70%.
    """
    if not payment:
        return

    invoice = getattr(payment, "invoice", None)
    order = getattr(invoice, "order", None) if invoice else None
    owner = getattr(order, "owner", None)
    if not owner:
        return

    if not can_access_feature(owner, "engine.payment_links").allowed:
        return

    flags = get_engine_flags()
    if not flags.enable_payment_commission:
        return

    amount = _q(getattr(payment, "amount", 0))
    platform_fee = (amount * (flags.payment_commission_percent / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    split = apply_profit_protection(
        gross_amount=platform_fee,
        min_company_share_percent=flags.min_company_share_percent,
        max_user_reward_percent=flags.max_user_reward_percent,
    )

    engine = get_or_create_engine_for_update(owner)
    engine.payment_commission_earned = _q(engine.payment_commission_earned) + split.user_share
    engine.admin_profit_formula = flags.profit_formula
    engine.save(update_fields=["payment_commission_earned", "admin_profit_formula", "updated_at"])

    EngineEventLog.objects.create(
        owner=owner,
        actor=actor,
        category=EngineEventLog.Category.FLOW,
        level=EngineEventLog.Level.INFO,
        event_key="payment.received",
        message="Payment received and commission recorded.",
        meta={
            "payment_id": getattr(payment, "id", None),
            "invoice_id": getattr(invoice, "id", None),
            "amount": str(amount),
            "platform_fee": str(split.gross),
            "user_commission": str(split.user_share),
            "company_share": str(split.company_share),
        },
    )


@transaction.atomic
def record_payment_link_paid(*, payment_link, actor=None) -> None:
    """
    Handle portal.PaymentLink status -> PAID transitions in an idempotent way.

    Some deployments may record payments via PaymentLink callbacks without creating
    a `commerce.Payment` row immediately. We use EngineEventLog as an idempotency
    guard to avoid double-crediting commissions.
    """
    if not payment_link:
        return

    owner = getattr(payment_link, "owner", None)
    if not owner:
        return

    if not can_access_feature(owner, "engine.payment_links").allowed:
        return

    flags = get_engine_flags()
    if not flags.enable_payment_commission:
        return

    # Idempotency: skip if already recorded.
    if EngineEventLog.objects.filter(owner=owner, event_key="payment_link.paid", object_id=str(getattr(payment_link, "id", ""))).exists():
        return

    amount = _q(getattr(payment_link, "amount", 0))
    platform_fee = (amount * (flags.payment_commission_percent / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    split = apply_profit_protection(
        gross_amount=platform_fee,
        min_company_share_percent=flags.min_company_share_percent,
        max_user_reward_percent=flags.max_user_reward_percent,
    )

    engine = get_or_create_engine_for_update(owner)
    engine.payment_commission_earned = _q(engine.payment_commission_earned) + split.user_share
    engine.admin_profit_formula = flags.profit_formula
    engine.save(update_fields=["payment_commission_earned", "admin_profit_formula", "updated_at"])

    EngineEventLog.objects.create(
        owner=owner,
        actor=actor,
        category=EngineEventLog.Category.FLOW,
        level=EngineEventLog.Level.INFO,
        event_key="payment_link.paid",
        message="PaymentLink paid and commission recorded.",
        meta={
            "payment_link_id": getattr(payment_link, "id", None),
            "invoice_id": getattr(payment_link, "invoice_id", None),
            "amount": str(amount),
            "platform_fee": str(split.gross),
            "user_commission": str(split.user_share),
            "company_share": str(split.company_share),
        },
        object_id=str(getattr(payment_link, "id", "")),
    )
