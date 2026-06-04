from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from khataapp.core_engine.models.engine import BusinessGrowthEngine
from khataapp.core_engine.models.logs import EngineEventLog
from khataapp.core_engine.models.referral import ReferralRecord
from khataapp.core_engine.services.admin_control import get_engine_flags
from khataapp.core_engine.services.plan_access import can_access_feature
from khataapp.core_engine.utils.engine import get_or_create_engine_for_update
from khataapp.core_engine.utils.profit import apply_profit_protection


def _q(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def resolve_referrer_by_code(code: str):
    code = (code or "").strip()
    if not code:
        return None
    engine = BusinessGrowthEngine.objects.filter(referral_code=code).select_related("owner").first()
    return engine.owner if engine else None


@transaction.atomic
def record_referral(*, referrer, referred, actor=None, meta: Optional[dict] = None) -> ReferralRecord | None:
    if not referrer or not referred or referrer == referred:
        return None
    if not can_access_feature(referrer, "engine.referrals").allowed:
        return None

    flags = get_engine_flags()
    if not flags.enable_referrals:
        return None

    try:
        rec = ReferralRecord.objects.create(
            referrer=referrer,
            referred=referred,
            status=ReferralRecord.Status.PENDING,
            commission_amount=Decimal("0.00"),
            meta=meta or {},
        )
    except IntegrityError:
        return ReferralRecord.objects.filter(referrer=referrer, referred=referred).first()

    EngineEventLog.objects.create(
        owner=referrer,
        actor=actor,
        category=EngineEventLog.Category.FLOW,
        level=EngineEventLog.Level.INFO,
        event_key="referral.recorded",
        message="Referral recorded (pending).",
        meta={"referred_user_id": referred.id, **(meta or {})},
    )
    return rec


@transaction.atomic
def pay_referral_commission(
    *,
    referral: ReferralRecord,
    gross_commission_amount,
    actor=None,
) -> ReferralRecord | None:
    """
    Mark a referral as PAID and credit referrer earnings (ProfitProtectionFormula applied).
    """
    if not referral:
        return None

    referrer = referral.referrer
    if not referrer:
        return None
    if not can_access_feature(referrer, "engine.referrals").allowed:
        return None

    flags = get_engine_flags()
    if not flags.enable_referrals:
        return None

    gross = _q(gross_commission_amount)
    split = apply_profit_protection(
        gross_amount=gross,
        min_company_share_percent=flags.min_company_share_percent,
        max_user_reward_percent=flags.max_user_reward_percent,
    )

    referral.commission_amount = split.user_share
    referral.status = ReferralRecord.Status.PAID
    referral.paid_at = timezone.now()
    referral.save(update_fields=["commission_amount", "status", "paid_at", "updated_at"])

    engine = get_or_create_engine_for_update(referrer)
    engine.referral_earnings = _q(engine.referral_earnings) + split.user_share
    engine.admin_profit_formula = flags.profit_formula
    engine.save(update_fields=["referral_earnings", "admin_profit_formula", "updated_at"])

    EngineEventLog.objects.create(
        owner=referrer,
        actor=actor,
        category=EngineEventLog.Category.AUDIT,
        level=EngineEventLog.Level.INFO,
        event_key="referral.paid",
        message="Referral commission paid.",
        meta={
            "referral_id": referral.id,
            "gross_commission": str(split.gross),
            "user_commission": str(split.user_share),
            "company_share": str(split.company_share),
            "referred_user_id": referral.referred_id,
        },
    )
    return referral

