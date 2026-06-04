# billing/signals.py
from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from django.db.utils import OperationalError, ProgrammingError

from .models import FeatureRegistry, Plan, PlanFeature, Subscription
from khataapp.models import UserProfile as KhataUserProfile
from .models import OrderItem


def _is_free_plan(p: Plan) -> bool:
    try:
        return (getattr(p, "price_monthly", 0) or 0) == 0 and (getattr(p, "price_yearly", 0) or 0) == 0 and (getattr(p, "price", 0) or 0) == 0
    except Exception:
        return False


@receiver(post_save, sender=Subscription)
def apply_subscription_groups(sender, instance: Subscription, created, **kwargs):
    """
    When a subscription is created or updated, make sure user's groups include the plan.groups.
    Also remove plan-groups that are no longer provided by any active subscription for that user.
    """
    user = instance.user

    # collect groups that should be present (union of groups from all active subscriptions)
    active_subs = Subscription.objects.filter(user=user, status="active").select_related("plan")
    allowed_groups = set()
    for s in active_subs:
        for g in s.plan.groups.all():
            allowed_groups.add(g)

    # add allowed groups
    for g in allowed_groups:
        user.groups.add(g)

    # remove groups that belong to any Plan but are not in allowed_groups
    all_plan_groups = set()
    for p in Plan.objects.all():
        for g in p.groups.all():
            all_plan_groups.add(g)

    for g in all_plan_groups:
        if g not in allowed_groups and g in user.groups.all():
            # only remove plan-owned groups (do not touch unrelated groups)
            user.groups.remove(g)


@receiver(post_delete, sender=Subscription)
def remove_subscription_groups_on_delete(sender, instance: Subscription, **kwargs):
    """
    When a subscription is deleted, recompute allowed groups and remove plan-groups not allowed anymore.
    """
    user = instance.user

    # FIX: use status="active" instead of active=True
    active_subs = Subscription.objects.filter(user=user, status="active").select_related("plan")
    allowed_groups = set()
    for s in active_subs:
        for g in s.plan.groups.all():
            allowed_groups.add(g)

    all_plan_groups = set()
    for p in Plan.objects.all():
        for g in p.groups.all():
            all_plan_groups.add(g)

    for g in all_plan_groups:
        if g not in allowed_groups and g in user.groups.all():
            user.groups.remove(g)

@receiver(post_save, sender=Subscription)
def update_user_profile_plan(sender, instance, **kwargs):
    profile, created = KhataUserProfile.objects.get_or_create(user=instance.user)
    if instance.plan and instance.status == "active":
        if profile.plan_id != instance.plan_id:
            profile.plan = instance.plan
            profile.save(update_fields=["plan"])

        # Keep accounts.UserProfile.plan in sync when it exists (admin often edits this model).
        try:
            from accounts.models import UserProfile as AccountsUserProfile

            acc_profile = AccountsUserProfile.objects.filter(user=instance.user).only("id", "plan_id").first()
            if acc_profile and acc_profile.plan_id != instance.plan_id:
                acc_profile.plan = instance.plan
                acc_profile.save(update_fields=["plan"])
        except Exception:
            pass


@receiver(post_save, sender=KhataUserProfile)
def sync_subscription_from_khata_profile(sender, instance: KhataUserProfile, created: bool, **kwargs):
    """
    Keep Subscription as the source of truth, but make admin/profile edits "take effect"
    by upgrading the active subscription when the khataapp profile plan changes.

    This fixes the common confusion where admins set `khataapp.UserProfile.plan` but
    `billing.services.get_effective_plan()` still uses an existing active Subscription.
    """
    if not instance or not instance.user_id or not instance.plan_id:
        return

    try:
        active_sub = (
            Subscription.objects.filter(user=instance.user, status="active")
            .order_by("-created_at", "-id")
            .only("id", "plan_id", "status")
            .first()
        )
        if active_sub and active_sub.plan_id == instance.plan_id:
            return

        from billing.services import upgrade_subscription

        upgrade_subscription(instance.user, instance.plan)
    except Exception:
        return


@receiver(post_save, sender="accounts.UserProfile")
def sync_subscription_from_accounts_profile(sender, instance, created: bool, **kwargs):
    """
    Same as `sync_subscription_from_khata_profile`, but for `accounts.UserProfile`.

    Many admin flows edit Accounts -> UserProfile -> plan, so we keep the active
    subscription (and thus `get_effective_plan()`) aligned with that selection.
    """
    if not instance or not getattr(instance, "user_id", None) or not getattr(instance, "plan_id", None):
        return

    try:
        active_sub = (
            Subscription.objects.filter(user=instance.user, status="active")
            .order_by("-created_at", "-id")
            .only("id", "plan_id", "status")
            .first()
        )
        if active_sub and active_sub.plan_id == instance.plan_id:
            return

        from billing.services import upgrade_subscription

        upgrade_subscription(instance.user, instance.plan)
    except Exception:
        return


@receiver(post_save, sender=Plan)
def ensure_plan_features_on_plan_save(sender, instance: Plan, created: bool, **kwargs):
    """
    Ensure newly created/updated plans have PlanFeature rows for all active features.

    Without this, plans created after the initial feature-registry sync may end up with
    missing PlanFeature rows, making `feature_allowed` return False for most features.
    """
    if not instance or not instance.pk:
        return
    try:
        from billing.services import sync_feature_registry

        sync_feature_registry()
    except Exception:
        # Best-effort; still try to backfill from already-existing FeatureRegistry rows.
        pass

    try:
        features = FeatureRegistry.objects.filter(active=True).only("id")
        default_enabled = not _is_free_plan(instance)
        with transaction.atomic():
            for feat in features:
                PlanFeature.objects.get_or_create(
                    plan=instance,
                    feature=feat,
                    defaults={"enabled": default_enabled},
                )
    except (OperationalError, ProgrammingError):
        return
    except Exception:
        return

@receiver(post_save, sender=OrderItem)
def update_order_total_on_save(sender, instance, **kwargs):
    order = instance.order
    order.update_total()
    order.save()

@receiver(post_delete, sender=OrderItem)
def update_order_total_on_delete(sender, instance, **kwargs):
    order = instance.order
    order.update_total()
    order.save()
