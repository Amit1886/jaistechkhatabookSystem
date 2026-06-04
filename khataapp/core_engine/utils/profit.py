from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


def _d(v) -> Decimal:
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _pct(amount: Decimal, percent: Decimal) -> Decimal:
    return (amount * percent / Decimal("100")).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class ProfitProtectionResult:
    gross: Decimal
    company_share: Decimal
    user_share: Decimal
    min_company_share_percent: Decimal
    max_user_reward_percent: Decimal


def apply_profit_protection(
    *,
    gross_amount,
    desired_user_share=None,
    desired_user_percent=None,
    min_company_share_percent=Decimal("70.00"),
    max_user_reward_percent=Decimal("30.00"),
) -> ProfitProtectionResult:
    """
    Enforce:
      - company_share >= 70% (configurable)
      - user_share <= 30% (configurable)
      - no negative values ever

    The caller supplies a "gross_amount" (e.g., platform fee) to split.
    """

    gross = _d(gross_amount)
    if gross <= 0:
        return ProfitProtectionResult(
            gross=Decimal("0.00"),
            company_share=Decimal("0.00"),
            user_share=Decimal("0.00"),
            min_company_share_percent=_d(min_company_share_percent),
            max_user_reward_percent=_d(max_user_reward_percent),
        )

    min_company_pct = max(Decimal("0.00"), min(Decimal("100.00"), _d(min_company_share_percent)))
    max_user_pct = max(Decimal("0.00"), min(Decimal("100.00"), _d(max_user_reward_percent)))

    # Company share constraint implies user_share <= (100 - min_company_pct)%
    allowed_user_pct = min(max_user_pct, Decimal("100.00") - min_company_pct)

    if desired_user_share is not None:
        desired_user = _d(desired_user_share)
    elif desired_user_percent is not None:
        desired_user = _pct(gross, _d(desired_user_percent))
    else:
        desired_user = _pct(gross, allowed_user_pct)

    desired_user = max(Decimal("0.00"), desired_user)
    max_user_amount = _pct(gross, allowed_user_pct)
    user_share = min(desired_user, max_user_amount)

    company_share = (gross - user_share).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    if company_share < 0:
        company_share = Decimal("0.00")
        user_share = gross

    # Final safety clamp.
    user_share = max(Decimal("0.00"), min(user_share, gross)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    company_share = (gross - user_share).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    return ProfitProtectionResult(
        gross=gross.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
        company_share=company_share,
        user_share=user_share,
        min_company_share_percent=min_company_pct,
        max_user_reward_percent=max_user_pct,
    )

