from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.roles import can_delete as erp_can_delete
from core_settings.services import apply_updates
from khataapp.models import Party, ReminderLog
from smart_khata.models import PaymentBehavior
from smart_khata.services.credit_score import update_party_credit_metrics
from smart_khata.services.reminders import (
    default_tone,
    reminder_channels,
    reminder_offsets,
    reminders_enabled,
    risk_threshold,
    smart_timing_enabled,
    template_for_tone,
)


@login_required
def customer_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Party.objects.filter(owner=request.user, party_type="customer").order_by("-total_due", "-credit_score", "name", "id")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(mobile__icontains=q) | Q(email__icontains=q))

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    return render(
        request,
        "smart_khata/customer_list.html",
        {"page_obj": page_obj, "customers": page_obj.object_list, "q": q},
    )


@login_required
def customer_profile(request, party_id: int):
    party = get_object_or_404(Party, id=int(party_id), owner=request.user, party_type="customer")

    score_res = update_party_credit_metrics(party)
    behaviors = (
        PaymentBehavior.objects.select_related("invoice")
        .filter(owner=request.user, customer=party)
        .order_by("-created_at", "-id")[:20]
    )
    reminders = (
        ReminderLog.objects.select_related("invoice")
        .filter(party=party, reminder_type="due")
        .order_by("-created_at", "-id")[:20]
    )

    from commerce.models import Invoice
    from smart_khata.services.credit_score import get_invoice_due_date

    invoices = (
        Invoice.objects.select_related("order")
        .prefetch_related("payments")
        .filter(order__owner=request.user, order__party=party, order__order_type__iexact="sale")
        .exclude(status__iexact="cancelled")
        .order_by("-created_at", "-id")[:25]
    )
    today = timezone.localdate()
    outstanding_invoices = []
    for inv in invoices:
        try:
            paid = sum((p.amount or Decimal("0.00")) for p in inv.payments.all() if not getattr(p, "is_deleted", False))
        except Exception:
            paid = Decimal("0.00")
        outstanding = (inv.amount or Decimal("0.00")) - paid
        if outstanding <= 0:
            continue
        due_dt = get_invoice_due_date(inv)
        outstanding_invoices.append(
            {
                "invoice": inv,
                "outstanding": outstanding,
                "due_date": due_dt,
                "days_overdue": (today - due_dt).days,
            }
        )

    return render(
        request,
        "smart_khata/customer_profile.html",
        {
            "party": party,
            "score": score_res,
            "behaviors": behaviors,
            "reminders": reminders,
            "outstanding_invoices": outstanding_invoices,
        },
    )


@login_required
def credit_score_dashboard(request):
    q = (request.GET.get("q") or "").strip()
    level = (request.GET.get("level") or "").strip().lower()
    recalc = (request.GET.get("recalc") or "").strip().lower() in {"1", "true", "yes", "on"}

    qs = Party.objects.filter(owner=request.user, party_type="customer").order_by("-credit_score", "-total_due", "name", "id")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(mobile__icontains=q) | Q(email__icontains=q))

    if level in {"excellent", "good", "risky", "high risk"}:
        # Filter by stored score thresholds to keep it fast.
        if level == "excellent":
            qs = qs.filter(credit_score__gte=80)
        elif level == "good":
            qs = qs.filter(credit_score__gte=60, credit_score__lt=80)
        elif level == "risky":
            qs = qs.filter(credit_score__gte=40, credit_score__lt=60)
        else:
            qs = qs.filter(credit_score__lt=40)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    # Optional recalculation for visible rows only (keeps UI responsive).
    if recalc:
        for c in page_obj.object_list:
            try:
                update_party_credit_metrics(c)
            except Exception:
                continue

    summary = {
        "excellent": Party.objects.filter(owner=request.user, party_type="customer", credit_score__gte=80).count(),
        "good": Party.objects.filter(owner=request.user, party_type="customer", credit_score__gte=60, credit_score__lt=80).count(),
        "risky": Party.objects.filter(owner=request.user, party_type="customer", credit_score__gte=40, credit_score__lt=60).count(),
        "high_risk": Party.objects.filter(owner=request.user, party_type="customer", credit_score__lt=40).count(),
    }

    return render(
        request,
        "smart_khata/credit_score_dashboard.html",
        {
            "page_obj": page_obj,
            "customers": page_obj.object_list,
            "q": q,
            "level": level,
            "summary": summary,
        },
    )


@login_required
def khata_reminder_settings(request):
    # Admin/user control: allow edit only for admin-level roles (existing ERP convention).
    can_edit = bool(erp_can_delete(request.user))

    if request.method == "POST":
        if not can_edit:
            messages.error(request, "Permission denied: admin access required.")
            return redirect("smart_khata:khata_reminder_settings")

        enabled = request.POST.get("enabled") == "on"
        smart_timing = request.POST.get("smart_timing") == "on"
        tone = (request.POST.get("default_tone") or "professional").strip().lower()
        if tone not in {"friendly", "professional", "strict"}:
            tone = "professional"

        # Offsets: accept comma separated integers
        offsets_raw = (request.POST.get("offsets") or "").strip()
        offsets = []
        for part in offsets_raw.replace("[", "").replace("]", "").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                offsets.append(int(part))
            except Exception:
                continue
        if not offsets:
            offsets = [-3, 0, 3, 7]

        channels = [c for c in request.POST.getlist("channels") if c in {"whatsapp", "sms", "email"}] or ["whatsapp"]

        tmpl_friendly = request.POST.get("tmpl_friendly") or ""
        tmpl_prof = request.POST.get("tmpl_professional") or ""
        tmpl_strict = request.POST.get("tmpl_strict") or ""

        try:
            thr = int((request.POST.get("risk_threshold") or "").strip() or 40)
        except Exception:
            thr = 40

        updates = [
            {"key": "khata_auto_reminders_enabled", "value": bool(enabled)},
            {"key": "khata_smart_timing_enabled", "value": bool(smart_timing)},
            {"key": "khata_default_tone", "value": tone},
            {"key": "khata_reminder_offsets", "value": offsets},
            {"key": "khata_reminder_channels", "value": channels},
            {"key": "khata_template_friendly", "value": str(tmpl_friendly)},
            {"key": "khata_template_professional", "value": str(tmpl_prof)},
            {"key": "khata_template_strict", "value": str(tmpl_strict)},
            {"key": "khata_risk_threshold", "value": int(thr)},
        ]
        apply_updates(request.user, updates)
        messages.success(request, "Khata reminder settings saved.")
        return redirect("smart_khata:khata_reminder_settings")

    return render(
        request,
        "smart_khata/khata_reminder_settings.html",
        {
            "can_edit": can_edit,
            "enabled": reminders_enabled(request.user),
            "smart_timing": smart_timing_enabled(request.user),
            "offsets": reminder_offsets(request.user),
            "channels": reminder_channels(request.user),
            "default_tone": default_tone(request.user),
            "risk_threshold": risk_threshold(request.user),
            "tmpl_friendly": template_for_tone(request.user, "friendly"),
            "tmpl_professional": template_for_tone(request.user, "professional"),
            "tmpl_strict": template_for_tone(request.user, "strict"),
        },
    )


@login_required
def reminder_logs(request):
    q = (request.GET.get("q") or "").strip()
    status_q = (request.GET.get("status") or "").strip().lower()
    channel = (request.GET.get("channel") or "").strip().lower()

    qs = ReminderLog.objects.select_related("party", "invoice").filter(party__owner=request.user, party__party_type="customer")
    if q:
        qs = qs.filter(
            Q(party__name__icontains=q)
            | Q(invoice__number__icontains=q)
            | Q(payload__icontains=q)
        )
    if status_q in {"scheduled", "sent", "failed", "skipped"}:
        qs = qs.filter(status=status_q)
    if channel in {"whatsapp", "sms", "email"}:
        qs = qs.filter(channel=channel)

    qs = qs.order_by("-created_at", "-id")
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(
        request,
        "smart_khata/reminder_logs.html",
        {
            "page_obj": page_obj,
            "logs": page_obj.object_list,
            "q": q,
            "status": status_q,
            "channel": channel,
        },
    )


# ---------------- Reports ----------------

@login_required
def report_credit_ranking(request):
    qs = Party.objects.filter(owner=request.user, party_type="customer").order_by("-credit_score", "-total_due", "name", "id")
    return render(request, "smart_khata/reports/credit_ranking.html", {"customers": qs[:500]})


@login_required
def report_high_risk_customers(request):
    thr = risk_threshold(request.user)
    qs = (
        Party.objects.filter(owner=request.user, party_type="customer", credit_score__lt=thr)
        .order_by("-total_due", "credit_score", "name", "id")
    )
    return render(request, "smart_khata/reports/high_risk_customers.html", {"customers": qs[:500], "threshold": thr})


@login_required
def report_late_payments(request):
    date_from = request.GET.get("from") or ""
    date_to = request.GET.get("to") or ""
    df = None
    dt = None
    try:
        if date_from:
            df = timezone.datetime.fromisoformat(date_from).date()
    except Exception:
        df = None
    try:
        if date_to:
            dt = timezone.datetime.fromisoformat(date_to).date()
    except Exception:
        dt = None

    qs = PaymentBehavior.objects.select_related("customer", "invoice").filter(owner=request.user, delay_days__gt=0)
    if df:
        qs = qs.filter(created_at__date__gte=df)
    if dt:
        qs = qs.filter(created_at__date__lte=dt)
    qs = qs.order_by("-created_at", "-delay_days")[:500]
    return render(
        request,
        "smart_khata/reports/late_payment_report.html",
        {"rows": qs, "from": df, "to": dt},
    )


@login_required
def report_reminder_activity(request):
    # Simple summary for the last 30 days.
    today = timezone.localdate()
    start = today - timedelta(days=30)
    channel = (request.GET.get("channel") or "").strip().lower()
    status_q = (request.GET.get("status") or "").strip().lower()

    base = ReminderLog.objects.filter(
        party__owner=request.user,
        created_at__date__gte=start,
        party__party_type="customer",
    )
    if channel in {"whatsapp", "sms", "email"}:
        base = base.filter(channel=channel)
    if status_q in {"scheduled", "sent", "failed", "skipped"}:
        base = base.filter(status=status_q)

    by_channel = base.values("channel").annotate(count=Count("id")).order_by("-count")
    by_status = base.values("status").annotate(count=Count("id")).order_by("-count")
    recent = base.select_related("party", "invoice").order_by("-created_at", "-id")[:50]

    return render(
        request,
        "smart_khata/reports/reminder_activity_report.html",
        {
            "start": start,
            "today": today,
            "by_channel": list(by_channel),
            "by_status": list(by_status),
            "recent": recent,
            "channel": channel,
            "status": status_q,
        },
    )
