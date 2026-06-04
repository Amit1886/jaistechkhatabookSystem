from __future__ import annotations

from django import forms

from khataapp.core_engine.models.settings import EngineControlPanelSettings


class EngineControlPanelSettingsForm(forms.ModelForm):
    class Meta:
        model = EngineControlPanelSettings
        fields = [
            "enabled",
            "enable_rewards",
            "enable_referrals",
            "enable_payment_commission",
            "enable_notifications",
            "enable_loyalty",
            "enable_daily_tasks",
            "enable_analytics",
            "invoice_reward_percent",
            "gst_invoice_bonus_points",
            "nongst_invoice_bonus_points",
            "payment_commission_percent",
            "min_company_share_percent",
            "max_user_reward_percent",
        ]
        widgets = {
            "invoice_reward_percent": forms.NumberInput(attrs={"step": "0.01"}),
            "payment_commission_percent": forms.NumberInput(attrs={"step": "0.01"}),
            "min_company_share_percent": forms.NumberInput(attrs={"step": "0.01"}),
            "max_user_reward_percent": forms.NumberInput(attrs={"step": "0.01"}),
        }

