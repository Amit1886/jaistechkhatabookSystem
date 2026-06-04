from __future__ import annotations

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from solo.models import SingletonModel


class EngineControlPanelSettings(SingletonModel):
    """
    Global master switches + rule configuration for BusinessGrowthEngine.

    Stored as a singleton so superadmins can operate a single control center.
    """

    enabled = models.BooleanField(default=True)

    enable_rewards = models.BooleanField(default=True)
    enable_referrals = models.BooleanField(default=True)
    enable_payment_commission = models.BooleanField(default=True)
    enable_notifications = models.BooleanField(default=True)
    enable_loyalty = models.BooleanField(default=True)
    enable_daily_tasks = models.BooleanField(default=True)
    enable_analytics = models.BooleanField(default=True)

    # Rewards rules (percent-based caps are enforced by ProfitProtectionFormula)
    invoice_reward_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Nominal rewards rate (percent of invoice amount) used to derive coins/points.",
    )
    gst_invoice_bonus_points = models.PositiveIntegerField(default=10)
    nongst_invoice_bonus_points = models.PositiveIntegerField(default=5)

    payment_commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Commission percent on successful payment receipts (for earnings dashboards).",
    )

    # Profit protection formula
    min_company_share_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("70.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    max_user_reward_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("30.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "engine_control_panel_settings"

    def __str__(self) -> str:
        return "Engine Control Panel Settings"

    def profit_formula_dict(self) -> dict:
        return {
            "min_company_share_percent": str(self.min_company_share_percent),
            "max_user_reward_percent": str(self.max_user_reward_percent),
        }

