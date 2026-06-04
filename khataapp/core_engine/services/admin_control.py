from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.utils import OperationalError, ProgrammingError

from khataapp.core_engine.models.settings import EngineControlPanelSettings


@dataclass(frozen=True)
class EngineFlags:
    enabled: bool = True
    enable_rewards: bool = True
    enable_referrals: bool = True
    enable_payment_commission: bool = True
    enable_notifications: bool = True
    enable_loyalty: bool = True
    enable_daily_tasks: bool = True
    enable_analytics: bool = True

    invoice_reward_percent: Decimal = Decimal("1.00")
    gst_invoice_bonus_points: int = 10
    nongst_invoice_bonus_points: int = 5
    payment_commission_percent: Decimal = Decimal("1.00")

    min_company_share_percent: Decimal = Decimal("70.00")
    max_user_reward_percent: Decimal = Decimal("30.00")

    @property
    def profit_formula(self) -> dict:
        return {
            "min_company_share_percent": str(self.min_company_share_percent),
            "max_user_reward_percent": str(self.max_user_reward_percent),
        }


def get_engine_flags() -> EngineFlags:
    """
    Read the singleton settings row, but never crash callers if the table isn't ready.
    """
    try:
        s = EngineControlPanelSettings.get_solo()
        return EngineFlags(
            enabled=bool(s.enabled),
            enable_rewards=bool(s.enable_rewards),
            enable_referrals=bool(s.enable_referrals),
            enable_payment_commission=bool(s.enable_payment_commission),
            enable_notifications=bool(s.enable_notifications),
            enable_loyalty=bool(s.enable_loyalty),
            enable_daily_tasks=bool(s.enable_daily_tasks),
            enable_analytics=bool(s.enable_analytics),
            invoice_reward_percent=Decimal(str(s.invoice_reward_percent or "0")),
            gst_invoice_bonus_points=int(s.gst_invoice_bonus_points or 0),
            nongst_invoice_bonus_points=int(s.nongst_invoice_bonus_points or 0),
            payment_commission_percent=Decimal(str(s.payment_commission_percent or "0")),
            min_company_share_percent=Decimal(str(s.min_company_share_percent or "70")),
            max_user_reward_percent=Decimal(str(s.max_user_reward_percent or "30")),
        )
    except (OperationalError, ProgrammingError):
        return EngineFlags()


def engine_enabled() -> bool:
    return bool(get_engine_flags().enabled)

