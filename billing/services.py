from datetime import timedelta
from threading import Lock

from django.db.utils import OperationalError
from django.db import transaction
from django.utils import timezone

from billing.models import (
    Plan,
    Subscription,
    FeatureRegistry,
    PlanFeature,
    SubscriptionHistory,
    UserFeatureOverride,
)


FEATURE_REGISTRY = [
    {"key": "billing.invoices", "label": "Invoices", "group": "Billing"},
    {"key": "billing.returns", "label": "Returns", "group": "Billing"},
    {"key": "billing.credit_notes", "label": "Credit Notes", "group": "Billing"},
    {"key": "billing.debit_notes", "label": "Debit Notes", "group": "Billing"},
    {"key": "commerce.orders", "label": "Orders", "group": "Commerce"},
    {"key": "commerce.purchase", "label": "Purchase", "group": "Commerce"},
    {"key": "commerce.suppliers", "label": "Suppliers", "group": "Commerce"},
    {"key": "portal.customer", "label": "Customer Portal", "group": "Portal"},
    {"key": "portal.supplier", "label": "Supplier Portal", "group": "Portal"},
    {"key": "portal.payments", "label": "Payment Links", "group": "Portal"},
    {"key": "commerce.inventory", "label": "Inventory", "group": "Inventory"},
    {"key": "procurement.supplier_compare", "label": "Supplier Price Comparison", "group": "Procurement"},
    {"key": "inventory.stock_transfer", "label": "Stock Transfer", "group": "Inventory"},
    {"key": "accounting.journal_vouchers", "label": "Journal Vouchers", "group": "Accounting"},
    {"key": "inventory.barcode", "label": "Barcode", "group": "Inventory"},
    {"key": "barcode.print", "label": "Barcode Print", "group": "Inventory"},
    {"key": "inventory.batch", "label": "Batch", "group": "Inventory"},
    {"key": "inventory.expiry", "label": "Expiry", "group": "Inventory"},
    {"key": "communication.whatsapp", "label": "WhatsApp Bot", "group": "Communication"},
    {"key": "whatsapp.orders", "label": "WhatsApp Orders", "group": "Communication"},
    {"key": "communication.sms", "label": "SMS", "group": "Communication"},
    {"key": "communication.email", "label": "Email", "group": "Communication"},
    {"key": "advanced.ai_reports", "label": "AI Reports", "group": "Advanced"},
    {"key": "ai.insights", "label": "AI Insights", "group": "AI Tools"},
    {"key": "ai.ocr", "label": "OCR Invoice Entry", "group": "AI Tools"},
    {"key": "ai.voice", "label": "Voice Accounting", "group": "AI Tools"},
    {"key": "ai.whatsapp", "label": "WhatsApp Accounting", "group": "AI Tools"},
    {"key": "ai.smart_alerts", "label": "Smart Alerts", "group": "AI Tools"},
    {"key": "advanced.api", "label": "API Access", "group": "Advanced"},
    {"key": "api.access", "label": "API Access", "group": "Advanced"},
    {"key": "advanced.automation", "label": "Automation", "group": "Advanced"},
    {"key": "automation.bank_import", "label": "Bank Statement Import", "group": "Automation"},
    {"key": "settings.advanced", "label": "Advanced Settings", "group": "Advanced"},
    {"key": "multiuser", "label": "Multi-user", "group": "Advanced"},
    {"key": "reports.advanced", "label": "Advanced Reports", "group": "Advanced"},
    {"key": "khata.credit_score", "label": "Customer Credit Score", "group": "Finance"},
    {"key": "khata.reminders", "label": "Auto Khata Reminders", "group": "Finance"},
    {"key": "reports.account_summary", "label": "Account Summary", "group": "Reports"},
    {"key": "reports.interest_calculation", "label": "Interest Calculation", "group": "Reports"},
    {"key": "reports.inventory_books", "label": "Inventory Books", "group": "Reports"},
    {"key": "reports.inventory_summary", "label": "Inventory Summary", "group": "Reports"},
    {"key": "reports.gst_report", "label": "GST Report", "group": "Reports"},
    {"key": "reports.mis_report", "label": "MIS Report", "group": "Reports"},
    {"key": "system.checklist", "label": "Checklist System", "group": "Reports"},
    {"key": "system.query", "label": "Query System", "group": "Reports"},
    {"key": "payments.gateway", "label": "Payment Gateway", "group": "Advanced"},
    {"key": "field.agents", "label": "Field Agents", "group": "Advanced"},
    {"key": "chatbot.flows", "label": "Chatbot Flows", "group": "Communication"},
    # Central Business Engine (Growth)
    {"key": "engine.rewards", "label": "Rewards Wallet", "group": "Growth Engine"},
    {"key": "engine.referrals", "label": "Referral Center", "group": "Growth Engine"},
    {"key": "engine.payment_links", "label": "Payment Earnings", "group": "Growth Engine"},
    {"key": "engine.notifications", "label": "WhatsApp/SMS Engine", "group": "Growth Engine"},
    {"key": "engine.loyalty", "label": "Loyalty & Offers", "group": "Growth Engine"},
    {"key": "engine.daily_tasks", "label": "Daily Tasks", "group": "Growth Engine"},
    {"key": "engine.analytics", "label": "Growth Analytics", "group": "Growth Engine"},
]


_registry_sync_lock = Lock()
_registry_synced = False


def sync_feature_registry():
    """
    Ensure FeatureRegistry/PlanFeature rows exist.

    Important: this function writes to DB. It must not be called repeatedly per-request
    (especially on SQLite). It is safe to call on-demand; it will run at most once
    per-process and is resilient to transient SQLite lock errors.
    """
    global _registry_synced
    if _registry_synced:
        return

    with _registry_sync_lock:
        if _registry_synced:
            return

        try:
            desired_keys = [x["key"] for x in FEATURE_REGISTRY]
            existing_keys = set(
                FeatureRegistry.objects.filter(key__in=desired_keys).values_list("key", flat=True)
            )
            needs_sync = len(existing_keys) != len(desired_keys)
            if not needs_sync:
                _registry_synced = True
                return

            for index, item in enumerate(FEATURE_REGISTRY):
                FeatureRegistry.objects.update_or_create(
                    key=item["key"],
                    defaults={
                        "label": item["label"],
                        "group": item.get("group", "General"),
                        "description": item.get("description", ""),
                        "sort_order": index,
                        "active": True,
                        "is_advanced": (item.get("group", "").strip().lower() in {"advanced", "ai tools"}),
                    },
                )
            def _is_free_plan(p: Plan) -> bool:
                try:
                    return (getattr(p, "price_monthly", 0) or 0) == 0 and (getattr(p, "price_yearly", 0) or 0) == 0 and (getattr(p, "price", 0) or 0) == 0
                except Exception:
                    return False

            # Ensure every plan has entries for newly added features.
            # Default: disable for Free plans so locked modules show "Upgrade required" by default.
            for plan in Plan.objects.all():
                default_enabled = not _is_free_plan(plan)
                for feature in FeatureRegistry.objects.filter(active=True):
                    PlanFeature.objects.get_or_create(plan=plan, feature=feature, defaults={"enabled": default_enabled})

            _registry_synced = True
        except OperationalError:
            # SQLite can throw "database is locked" under concurrent access.
            # Don't crash templates/pages; callers should behave read-only on failure.
            return


def ensure_user_feature_overrides(user, *, sync_plan: bool = True) -> dict:
    """
    Guarantee that every active FeatureRegistry row appears for the user under "Features & Services"
    without requiring developers to write new code.

    Behavior:
    - Creates missing UserFeatureOverride rows for all active features (note="auto").
    - If `sync_plan=True`, updates ONLY `note="auto"` overrides to follow the user's current plan.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return {"created": 0, "updated": 0}

    try:
        sync_feature_registry()
    except Exception:
        pass

    plan = get_effective_plan(user)
    enabled_by_plan = set()
    if plan:
        enabled_by_plan = set(
            PlanFeature.objects.filter(plan=plan, enabled=True).values_list("feature_id", flat=True)
        )

    created = 0
    updated = 0
    for feature in FeatureRegistry.objects.filter(active=True).order_by("group", "sort_order", "id"):
        default_enabled = True if not plan else (feature.id in enabled_by_plan)
        obj, was_created = UserFeatureOverride.objects.get_or_create(
            user=user,
            feature=feature,
            defaults={"is_enabled": default_enabled, "note": "auto"},
        )
        if was_created:
            created += 1
        elif sync_plan and (obj.note or "").strip().lower() == "auto" and obj.is_enabled != default_enabled:
            obj.is_enabled = default_enabled
            obj.save(update_fields=["is_enabled", "updated_at"])
            updated += 1

    return {"created": created, "updated": updated}


def enable_feature_dependencies_for_user(user, feature_id: int) -> int:
    """
    When enabling a feature for a user, auto-enable its dependencies (and their dependencies).

    Returns: number of overrides updated/created.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return 0

    try:
        feature = FeatureRegistry.objects.get(id=feature_id, active=True)
    except Exception:
        return 0

    try:
        deps = list(feature.dependencies.filter(active=True).values_list("id", flat=True))
    except Exception:
        deps = []

    if not deps:
        return 0

    changed = 0
    # Ensure override rows exist first
    ensure_user_feature_overrides(user, sync_plan=False)

    seen = set()
    stack = list(deps)
    while stack:
        dep_id = stack.pop()
        if dep_id in seen:
            continue
        seen.add(dep_id)
        try:
            dep = FeatureRegistry.objects.get(id=dep_id, active=True)
        except Exception:
            continue

        obj, _ = UserFeatureOverride.objects.get_or_create(
            user=user, feature=dep, defaults={"is_enabled": True, "note": "auto_dependency"}
        )
        if not obj.is_enabled:
            obj.is_enabled = True
            if (obj.note or "").strip().lower() == "auto":
                obj.note = "auto_dependency"
            obj.save(update_fields=["is_enabled", "note", "updated_at"])
            changed += 1

        # next level deps
        try:
            stack.extend(list(dep.dependencies.filter(active=True).values_list("id", flat=True)))
        except Exception:
            pass

    return changed


def get_active_subscription(user):
    return Subscription.objects.filter(user=user, status="active").select_related("plan").first()


def get_effective_plan(user):
    """
    Resolve the plan to use for permissions.

    Order:
    - Active subscription plan (if any)
    - UserProfile.plan (khataapp user profile plan assignment)
    - Group-mapped plan (billing.Plan.groups)

    Note: superusers are treated as allowed everywhere and typically do not require a plan.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None

    subscription = get_active_subscription(user)
    if subscription and subscription.plan:
        return subscription.plan

    # UserProfile.plan is a common single-source of truth in UI code paths.
    try:
        from khataapp.models import UserProfile

        profile = UserProfile.objects.filter(user=user).select_related("plan").first()
        if profile and profile.plan and profile.plan.active:
            return profile.plan
    except Exception:
        # Avoid failing requests if khataapp is unavailable during migrations/imports.
        pass

    # If the user belongs to a group assigned to a plan, pick the highest plan deterministically.
    # This enables "group plan permission" without requiring an active Subscription row.
    group_ids = user.groups.values_list("id", flat=True)
    plan = (
        Plan.objects.filter(active=True, groups__id__in=group_ids)
        .distinct()
        .order_by("-price_monthly", "-price_yearly", "-price", "-id")
        .first()
    )
    return plan


def user_has_feature(user, feature_key):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    try:
        sync_feature_registry()
    except OperationalError:
        pass
    override = UserFeatureOverride.objects.filter(
        user=user, feature__key=feature_key
    ).select_related("feature").first()
    if override is not None:
        return override.is_enabled

    plan = get_effective_plan(user)
    if not plan:
        return False
    return PlanFeature.objects.filter(plan=plan, feature__key=feature_key, enabled=True).exists()


def get_locked_feature_count(user):
    try:
        sync_feature_registry()
    except OperationalError:
        pass

    plan = get_effective_plan(user)
    if not plan:
        return FeatureRegistry.objects.filter(active=True).count()
    enabled_keys = PlanFeature.objects.filter(plan=plan, enabled=True).values_list("feature__key", flat=True)
    return FeatureRegistry.objects.filter(active=True).exclude(key__in=enabled_keys).count()


def get_usage_summary(user):
    # Placeholder for usage meters; can be expanded later.
    return {
        "usage": 12,
        "limit": 100,
    }


@transaction.atomic
def ensure_free_plan(user):
    free_plan = Plan.objects.filter(price_monthly=0, price_yearly=0, active=True).order_by("id").first()
    if not free_plan:
        free_plan = Plan.objects.create(
            name="Free",
            price=0,
            price_monthly=0,
            price_yearly=0,
            trial_days=0,
            active=True,
        )
    try:
        if hasattr(user, "userprofile") and user.userprofile:
            user.userprofile.plan = free_plan
            user.userprofile.save(update_fields=["plan"])
    except Exception:
        pass
    subscription = Subscription.objects.filter(user=user, status="active").first()
    if not subscription:
        subscription = Subscription.objects.create(
            user=user,
            plan=free_plan,
            status="active",
            start_date=timezone.now(),
        )
        SubscriptionHistory.objects.create(
            user=user,
            plan=free_plan,
            event_type="created",
            details={"source": "auto_free_plan"},
        )
    return subscription


def upgrade_subscription(user, plan):
    subscription = Subscription.objects.filter(user=user).order_by("-created_at").first()
    if subscription:
        subscription.plan = plan
        subscription.status = "active"
        subscription.start_date = timezone.now()
        if plan.trial_days:
            subscription.trial_end = timezone.now() + timedelta(days=plan.trial_days)
        subscription.save()
    else:
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            status="active",
            start_date=timezone.now(),
        )
    SubscriptionHistory.objects.create(
        user=user,
        plan=plan,
        event_type="upgraded",
        details={"source": "upgrade_flow"},
    )
    return subscription
