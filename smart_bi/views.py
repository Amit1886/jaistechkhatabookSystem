from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Expense
from commerce.models import Invoice, Order
from smart_bi.forms import DuplicateInvoiceSettingsForm, FestivalCampaignForm
from smart_bi.models import DuplicateInvoiceLog, DuplicateInvoiceSettings, FestivalCampaign
from smart_bi.services.business_health import get_chart_series, health_level, upsert_business_metric
from smart_bi.services.advisor import advisor_suggestions
from smart_bi.services.festival import get_active_campaign, suggested_campaigns_for


def _month_shift(year: int, month: int, delta_months: int) -> tuple[int, int]:
    total = (year * 12) + (month - 1) + int(delta_months)
    new_year = total // 12
    new_month = (total % 12) + 1
    return new_year, new_month


def _month_starts(end_day: date_type, count: int) -> list[date_type]:
    if count <= 0:
        return []
    end_year = end_day.year
    end_month = end_day.month
    starts: list[date_type] = []
    for i in range(count - 1, -1, -1):
        y, m = _month_shift(end_year, end_month, -i)
        starts.append(date_type(y, m, 1))
    return starts


@login_required
def business_health_dashboard(request):
    owner = request.user
    today = timezone.localdate()

    metric = upsert_business_metric(owner, day=today)
    level = health_level(metric.health_score)
    series = get_chart_series(owner, day=today)
    tips = advisor_suggestions(owner, metric=metric)

    # Monthly series (last 6 months)
    month_starts = _month_starts(today, 6)
    start_month = month_starts[0] if month_starts else today.replace(day=1)

    sales_rows = (
        Invoice.objects.filter(order__owner=owner, order__order_type="SALE", created_at__date__gte=start_month)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(t=Sum("amount"))
        .order_by("m")
    )
    purchase_rows = (
        Invoice.objects.filter(order__owner=owner, order__order_type="PURCHASE", created_at__date__gte=start_month)
        .annotate(m=TruncMonth("created_at"))
        .values("m")
        .annotate(t=Sum("amount"))
        .order_by("m")
    )
    expense_rows = (
        Expense.objects.filter(created_by=owner, expense_date__gte=start_month)
        .annotate(m=TruncMonth("expense_date"))
        .values("m")
        .annotate(t=Sum("amount_paid"))
        .order_by("m")
    )

    def _as_month_start(v):
        if hasattr(v, "date"):
            return v.date()
        return v

    sales_by_month = {_as_month_start(r["m"]): (r["t"] or Decimal("0.00")) for r in sales_rows if r.get("m")}
    purchase_by_month = {_as_month_start(r["m"]): (r["t"] or Decimal("0.00")) for r in purchase_rows if r.get("m")}
    expense_by_month = {_as_month_start(r["m"]): (r["t"] or Decimal("0.00")) for r in expense_rows if r.get("m")}

    monthly_labels: list[str] = []
    monthly_sales: list[str] = []
    monthly_expense: list[str] = []
    monthly_profit: list[str] = []
    for ms in month_starts:
        monthly_labels.append(ms.strftime("%b %Y"))
        s = sales_by_month.get(ms, Decimal("0.00"))
        p = purchase_by_month.get(ms, Decimal("0.00"))
        e = expense_by_month.get(ms, Decimal("0.00"))
        prof = (s - p - e).quantize(Decimal("0.01"))
        monthly_sales.append(str(s.quantize(Decimal("0.01"))))
        monthly_expense.append(str(e.quantize(Decimal("0.01"))))
        monthly_profit.append(str(prof))

    return render(
        request,
        "smart_bi/business_health_dashboard.html",
        {
            "metric": metric,
            "level": level,
            "series": series,
            "tips": tips,
            "monthly": {
                "labels": monthly_labels,
                "sales": monthly_sales,
                "expense": monthly_expense,
                "profit": monthly_profit,
            },
        },
    )


@login_required
def smart_bi_dashboard(request):
    owner = request.user
    today = timezone.localdate()
    metric = upsert_business_metric(owner, day=today)
    lvl = health_level(metric.health_score)
    festival = get_active_campaign(owner, day=today)
    dup_count = DuplicateInvoiceLog.objects.filter(owner=owner).count()
    return render(
        request,
        "smart_bi/dashboard.html",
        {
            "metric": metric,
            "level": lvl,
            "festival": festival,
            "dup_count": dup_count,
        },
    )


@login_required
def festival_campaign_list(request):
    owner = request.user
    today = timezone.localdate()
    campaigns = FestivalCampaign.objects.filter(owner=owner).prefetch_related("products").order_by("-start_date", "-id")
    return render(
        request,
        "smart_bi/festival_campaign_list.html",
        {
            "campaigns": campaigns,
            "today": today,
        },
    )


@login_required
def festival_campaign_create(request):
    owner = request.user
    if request.method == "POST":
        form = FestivalCampaignForm(request.POST, request.FILES, owner=owner)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.owner = owner
            campaign.save()
            form.save_m2m()

            # Keep only one ACTIVE campaign per owner (best-effort).
            if campaign.status == FestivalCampaign.Status.ACTIVE:
                FestivalCampaign.objects.filter(owner=owner).exclude(id=campaign.id).update(status=FestivalCampaign.Status.INACTIVE)

            messages.success(request, "Festival campaign saved.")
            return redirect("smart_bi:festival_campaign_list")
    else:
        form = FestivalCampaignForm(owner=owner)

    return render(
        request,
        "smart_bi/festival_campaign_create.html",
        {
            "form": form,
            "suggestions": suggested_campaigns_for(),
        },
    )


@login_required
@require_POST
def festival_campaign_action(request, campaign_id: int):
    owner = request.user
    campaign = get_object_or_404(FestivalCampaign, id=campaign_id, owner=owner)
    action = (request.POST.get("action") or "").strip().lower()

    if action == "activate":
        campaign.status = FestivalCampaign.Status.ACTIVE
        campaign.save(update_fields=["status", "updated_at"])
        FestivalCampaign.objects.filter(owner=owner).exclude(id=campaign.id).update(status=FestivalCampaign.Status.INACTIVE)
        messages.success(request, f"{campaign.name} activated.")
    elif action == "deactivate":
        campaign.status = FestivalCampaign.Status.INACTIVE
        campaign.save(update_fields=["status", "updated_at"])
        messages.success(request, f"{campaign.name} deactivated.")
    else:
        messages.error(request, "Invalid action.")

    return redirect("smart_bi:festival_campaign_list")


@login_required
def festival_sales_report(request):
    owner = request.user
    campaign_id_raw = (request.GET.get("campaign_id") or "").strip()

    campaign = None
    if campaign_id_raw:
        try:
            campaign_id = int(campaign_id_raw)
        except Exception:
            campaign_id = None
        if campaign_id:
            campaign = FestivalCampaign.objects.filter(id=campaign_id, owner=owner).first()

    if campaign is None:
        campaign = get_active_campaign(owner) or FestivalCampaign.objects.filter(owner=owner).order_by("-start_date", "-id").first()

    if not campaign:
        messages.info(request, "No festival campaigns found. Create one to view reports.")
        return redirect("smart_bi:festival_campaign_create")

    invoices = (
        Invoice.objects.select_related("order", "order__party")
        .filter(order__owner=owner, order__order_type="SALE", order__festival_campaign=campaign)
        .order_by("-created_at", "-id")
    )
    orders = Order.objects.filter(owner=owner, order_type="SALE", festival_campaign=campaign)

    total_sales = invoices.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
    total_discount = orders.aggregate(t=Sum("festival_discount_amount"))["t"] or Decimal("0.00")
    invoice_count = invoices.count()

    daily_rows = (
        invoices.annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(t=Sum("amount"))
        .order_by("d")
    )
    daily_labels = []
    daily_values = []
    for r in daily_rows:
        d = r.get("d")
        if not d:
            continue
        label = d.strftime("%d %b") if hasattr(d, "strftime") else str(d)
        daily_labels.append(label)
        daily_values.append(str((r.get("t") or Decimal("0.00")).quantize(Decimal("0.01"))))

    return render(
        request,
        "smart_bi/festival_sales_report.html",
        {
            "campaign": campaign,
            "campaigns": FestivalCampaign.objects.filter(owner=owner).order_by("-start_date", "-id"),
            "invoices": invoices[:200],
            "total_sales": total_sales.quantize(Decimal("0.01")),
            "total_discount": total_discount.quantize(Decimal("0.01")),
            "invoice_count": invoice_count,
            "chart": {"labels": daily_labels, "values": daily_values},
        },
    )


@login_required
def duplicate_invoice_report(request):
    owner = request.user
    logs = (
        DuplicateInvoiceLog.objects.select_related(
            "invoice",
            "invoice__order",
            "invoice__order__party",
            "possible_duplicate",
            "possible_duplicate__order",
            "possible_duplicate__order__party",
        )
        .filter(owner=owner)
        .order_by("-created_at", "-id")[:200]
    )
    return render(
        request,
        "smart_bi/duplicate_invoice_report.html",
        {
            "logs": logs,
        },
    )


@login_required
def duplicate_invoice_settings(request):
    owner = request.user
    settings_obj = DuplicateInvoiceSettings.get_for_owner(owner)
    if request.method == "POST":
        form = DuplicateInvoiceSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Duplicate invoice settings updated.")
            return redirect("smart_bi:duplicate_invoice_settings")
    else:
        form = DuplicateInvoiceSettingsForm(instance=settings_obj)

    return render(
        request,
        "smart_bi/duplicate_invoice_settings.html",
        {
            "form": form,
            "settings_obj": settings_obj,
        },
    )
