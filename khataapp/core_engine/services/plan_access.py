from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.core.exceptions import PermissionDenied

from billing.models import FeatureRegistry
from billing.services import get_effective_plan, user_has_feature
from khataapp.core_engine.services.admin_control import get_engine_flags


ENGINE_FEATURE_KEYS = (
    "engine.rewards",
    "engine.referrals",
    "engine.payment_links",
    "engine.notifications",
    "engine.loyalty",
    "engine.daily_tasks",
    "engine.analytics",
)


@dataclass(frozen=True)
class FeatureGateDecision:
    allowed: bool
    reason: str = ""
    feature_key: str = ""


def _admin_override(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False) and (user.is_superuser or user.is_staff))


def _settings_allows(feature_key: str) -> bool:
    flags = get_engine_flags()
    if not flags.enabled:
        return False
    mapping = {
        "engine.rewards": flags.enable_rewards,
        "engine.referrals": flags.enable_referrals,
        "engine.payment_links": flags.enable_payment_commission,
        "engine.notifications": flags.enable_notifications,
        "engine.loyalty": flags.enable_loyalty,
        "engine.daily_tasks": flags.enable_daily_tasks,
        "engine.analytics": flags.enable_analytics,
    }
    return bool(mapping.get(feature_key, True))


def can_access_feature(user, feature_key: str) -> FeatureGateDecision:
    if _admin_override(user):
        return FeatureGateDecision(allowed=True, reason="admin_override", feature_key=feature_key)

    if not user or not getattr(user, "is_authenticated", False):
        return FeatureGateDecision(allowed=False, reason="not_authenticated", feature_key=feature_key)

    if not _settings_allows(feature_key):
        return FeatureGateDecision(allowed=False, reason="disabled_by_admin", feature_key=feature_key)

    # Plan feature gates (billing FeatureRegistry / PlanFeature).
    # Safety fallback: if the feature is not registered in the FeatureRegistry yet,
    # do not block access (avoids breaking legacy flows during rollout).
    if FeatureRegistry.objects.filter(key=feature_key, active=True).exists():
        if not user_has_feature(user, feature_key):
            return FeatureGateDecision(allowed=False, reason="plan_locked", feature_key=feature_key)

    return FeatureGateDecision(allowed=True, reason="ok", feature_key=feature_key)


def require_feature(user, feature_key: str) -> None:
    decision = can_access_feature(user, feature_key)
    if not decision.allowed:
        raise PermissionDenied(f"Feature locked: {feature_key} ({decision.reason})")


def get_locked_engine_features(user, feature_keys: Iterable[str] = ENGINE_FEATURE_KEYS) -> list[str]:
    if _admin_override(user):
        return []
    locked: list[str] = []
    for key in feature_keys:
        if not can_access_feature(user, key).allowed:
            locked.append(key)
    return locked


def get_user_plan_label(user) -> str:
    plan = get_effective_plan(user)
    return getattr(plan, "name", "") or "Free"
