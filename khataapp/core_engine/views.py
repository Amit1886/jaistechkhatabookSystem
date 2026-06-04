from __future__ import annotations

from datetime import timedelta
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from billing.services import get_effective_plan
from commerce.models import Invoice, Payment
from khataapp.core_engine.models.engine import BusinessGrowthEngine
from khataapp.core_engine.models.logs import RewardLedgerEntry
from khataapp.core_engine.models.loyalty import LoyaltyAccount
from khataapp.core_engine.models.referral import ReferralRecord
from khataapp.core_engine.models.tasks import DailyTaskCompletion, DailyTaskDefinition
from khataapp.core_engine.services.admin_control import get_engine_flags
from khataapp.core_engine.services.analytics_service import update_engine_snapshot
from khataapp.core_engine.services.daily_tasks import complete_task, ensure_default_tasks
from khataapp.core_engine.services.plan_access import get_locked_engine_features, require_feature
from khataapp.core_engine.services.referral_service import record_referral, resolve_referrer_by_code
from khataapp.core_engine.utils.profit import apply_profit_protection


def _get_or_create_engine(owner) -> BusinessGrowthEngine:
    engine, _ = BusinessGrowthEngine.objects.get_or_create(owner=owner)
    return engine


def _redirect_locked(request, feature_key: str):
    messages.info(request, f"Upgrade required to access: {feature_key}")
    return redirect("central_engine:feature_unlock_panel")


@login_required
def dashboard(request):
    engine = _get_or_create_engine(request.user)
    flags = get_engine_flags()
    snap = update_engine_snapshot(request.user)

    today = timezone.localdate()
    start = today - timedelta(days=6)
    daily_rows = (
        Invoice.objects.filter(order__owner=request.user, order__order_type="SALE", created_at__date__gte=start)
        .annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(t=Sum("amount"))
        .order_by("d")
    )
    labels: list[str] = []
    values: list[float] = []
    for r in daily_rows:
        d = r.get("d")
        if not d:
            continue
        labels.append(d.strftime("%d %b"))
        values.append(float((r.get("t") or Decimal("0.00")).quantize(Decimal("0.01"))))

    return render(
        request,
        "central_engine/dashboard.html",
        {
            "engine": engine,
            "flags": flags,
            "snapshot": snap.payload,
            "tips": snap.tips,
            "chart": {"labels_json": json.dumps(labels), "values_json": json.dumps(values)},
        },
    )


@login_required
def rewards_wallet(request):
    try:
        require_feature(request.user, "engine.rewards")
    except PermissionDenied:
        return _redirect_locked(request, "engine.rewards")

    engine = _get_or_create_engine(request.user)
    entries = RewardLedgerEntry.objects.filter(owner=request.user).order_by("-created_at", "-id")[:200]
    return render(
        request,
        "central_engine/rewards_wallet.html",
        {
            "engine": engine,
            "entries": entries,
        },
    )


@login_required
def referral_center(request):
    try:
        require_feature(request.user, "engine.referrals")
    except PermissionDenied:
        return _redirect_locked(request, "engine.referrals")

    engine = _get_or_create_engine(request.user)
    if request.method == "POST":
        code = (request.POST.get("referral_code") or "").strip()
        referrer = resolve_referrer_by_code(code)
        if not referrer:
            messages.error(request, "Invalid referral code.")
        else:
            record_referral(referrer=referrer, referred=request.user, actor=request.user, meta={"source": "manual_apply"})
            messages.success(request, "Referral applied.")
        return redirect("central_engine:referral_center")

    referrals = ReferralRecord.objects.filter(referrer=request.user).select_related("referred").order_by("-created_at", "-id")[:200]
    referred_by = ReferralRecord.objects.filter(referred=request.user).select_related("referrer").first()
    return render(
        request,
        "central_engine/referral_center.html",
        {
            "engine": engine,
            "referrals": referrals,
            "referred_by": referred_by,
        },
    )


@login_required
def loyalty_offers(request):
    try:
        require_feature(request.user, "engine.loyalty")
    except PermissionDenied:
        return _redirect_locked(request, "engine.loyalty")

    accounts = (
        LoyaltyAccount.objects.filter(owner=request.user)
        .select_related("party")
        .order_by("-points", "-updated_at")[:50]
    )
    return render(
        request,
        "central_engine/loyalty_offers.html",
        {
            "accounts": accounts,
        },
    )


@login_required
def payment_earnings(request):
    try:
        require_feature(request.user, "engine.payment_links")
    except PermissionDenied:
        return _redirect_locked(request, "engine.payment_links")

    engine = _get_or_create_engine(request.user)
    payments = (
        Payment.objects.filter(invoice__order__owner=request.user, is_deleted=False)
        .select_related("invoice", "invoice__order")
        .order_by("-created_at", "-id")[:200]
    )
    return render(
        request,
        "central_engine/payment_earnings.html",
        {
            "engine": engine,
            "payments": payments,
        },
    )


@login_required
def task_center(request):
    try:
        require_feature(request.user, "engine.daily_tasks")
    except PermissionDenied:
        return _redirect_locked(request, "engine.daily_tasks")

    ensure_default_tasks()
    engine = _get_or_create_engine(request.user)
    today = timezone.localdate()
    tasks = DailyTaskDefinition.objects.filter(is_active=True).order_by("sort_order", "id")
    completed = set(
        DailyTaskCompletion.objects.filter(owner=request.user, day=today).values_list("task__key", flat=True)
    )
    return render(
        request,
        "central_engine/task_center.html",
        {
            "engine": engine,
            "tasks": tasks,
            "completed": completed,
            "today": today,
        },
    )


@login_required
@require_POST
def complete_task_view(request):
    task_key = (request.POST.get("task_key") or "").strip()
    ok = complete_task(owner=request.user, task_key=task_key, actor=request.user)
    if ok:
        messages.success(request, "Task completed.")
    else:
        messages.info(request, "Task already completed (or unavailable).")
    return redirect("central_engine:task_center")


@login_required
def analytics_snapshot(request):
    try:
        require_feature(request.user, "engine.analytics")
    except PermissionDenied:
        return _redirect_locked(request, "engine.analytics")

    engine = _get_or_create_engine(request.user)
    snap = update_engine_snapshot(request.user)
    return render(
        request,
        "central_engine/analytics_snapshot.html",
        {
            "engine": engine,
            "snapshot": snap.payload,
            "tips": snap.tips,
        },
    )


@login_required
def feature_unlock_panel(request):
    engine = _get_or_create_engine(request.user)
    locked = get_locked_engine_features(request.user)
    plan = get_effective_plan(request.user)
    return render(
        request,
        "central_engine/feature_unlock_panel.html",
        {
            "engine": engine,
            "locked": locked,
            "plan": plan,
        },
    )


@login_required
def profit_preview(request):
    engine = _get_or_create_engine(request.user)
    flags = get_engine_flags()

    gross_raw = (request.GET.get("gross") or "").strip()
    result = None
    if gross_raw:
        try:
            gross = Decimal(gross_raw)
        except Exception:
            gross = None
        if gross is not None:
            result = apply_profit_protection(
                gross_amount=gross,
                min_company_share_percent=flags.min_company_share_percent,
                max_user_reward_percent=flags.max_user_reward_percent,
            )
        else:
            messages.error(request, "Invalid gross amount.")

    return render(
        request,
        "central_engine/profit_preview.html",
        {
            "engine": engine,
            "flags": flags,
            "result": result,
            "gross": gross_raw,
        },
    )
