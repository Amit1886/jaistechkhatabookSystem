from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db.models import Sum

from commerce.models import Invoice, Order
from smart_bi.models import DuplicateInvoiceSettings, FestivalCampaign
from smart_bi.services.business_health import get_chart_series, health_level, upsert_business_metric
from smart_bi.services.duplicate_invoices import find_possible_duplicate_invoices
from smart_bi.services.festival import apply_festival_discount, get_active_campaign, suggested_campaigns_for


def _read_payload(request) -> dict:
    if request.method != "POST":
        return {}
    try:
        if (request.content_type or "").lower().startswith("application/json"):
            return json.loads(request.body.decode("utf-8") or "{}") or {}
    except Exception:
        return {}
    return request.POST.dict()


@login_required
@require_http_methods(["GET", "POST"])
def api_check_duplicate_invoice(request):
    payload = _read_payload(request)
    order_id = (payload.get("order_id") or payload.get("order") or request.GET.get("order_id") or request.GET.get("order") or "").strip()
    if not order_id:
        return JsonResponse({"detail": "order_id is required"}, status=400)
    try:
        oid = int(order_id)
    except Exception:
        return JsonResponse({"detail": "Invalid order_id"}, status=400)

    order = get_object_or_404(Order.objects.select_related("party").prefetch_related("items__product"), id=oid, owner=request.user)

    # Match UI behavior: apply festival discount if applicable before checking.
    try:
        apply_festival_discount(order, day=timezone.localdate(), save=True)
    except Exception:
        pass

    settings = DuplicateInvoiceSettings.get_for_owner(request.user)
    candidates = find_possible_duplicate_invoices(order=order, settings=settings, max_results=10)

    return JsonResponse(
        {
            "order_id": order.id,
            "customer": {"id": order.party_id, "name": order.party.name if order.party else ""},
            "amount": str(order.total_amount().quantize(Decimal("0.01"))),
            "settings": {
                "enabled": bool(settings.enabled),
                "window_minutes": int(settings.window_minutes or 0),
                "strict_mode": bool(settings.strict_mode),
                "similarity_threshold": str(settings.similarity_threshold),
            },
            "has_duplicate": bool(candidates),
            "possible_duplicates": [
                {
                    "invoice_id": c.invoice.id,
                    "invoice_number": c.invoice.number,
                    "customer": c.invoice.order.party.name if c.invoice.order and c.invoice.order.party else "",
                    "products": c.product_summary,
                    "total_amount": str((c.invoice.amount or Decimal("0.00")).quantize(Decimal("0.01"))),
                    "created_at": c.invoice.created_at.isoformat() if c.invoice.created_at else "",
                    "similarity_score": str(c.similarity_score),
                    "view_url": reverse("commerce:invoice_view", args=[c.invoice.id]),
                }
                for c in candidates
            ],
        }
    )


@login_required
@require_http_methods(["GET"])
def api_business_health(request):
    owner = request.user
    today = timezone.localdate()
    metric = upsert_business_metric(owner, day=today)
    lvl = health_level(metric.health_score)
    series = get_chart_series(owner, day=today)
    return JsonResponse(
        {
            "date": str(today),
            "score": int(metric.health_score),
            "level": {"label": lvl.label, "css_class": lvl.css_class},
            "metrics": {
                "total_sales": str(metric.total_sales),
                "total_profit": str(metric.total_profit),
                "total_expense": str(metric.total_expense),
                "outstanding_due": str(metric.outstanding_due),
                "stock_value": str(metric.stock_value),
            },
            "series": series,
        }
    )


@login_required
@require_http_methods(["GET"])
def api_festival_active(request):
    owner = request.user
    today = timezone.localdate()
    campaign = get_active_campaign(owner, day=today)
    if not campaign:
        return JsonResponse(
            {
                "active": False,
                "today": str(today),
                "suggestions": suggested_campaigns_for(today),
            }
        )

    return JsonResponse(
        {
            "active": True,
            "today": str(today),
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "start_date": str(campaign.start_date),
                "end_date": str(campaign.end_date),
                "discount_type": campaign.discount_type,
                "discount_value": str(campaign.discount_value),
                "theme": campaign.theme,
                "status": campaign.status,
                "banner_url": (campaign.banner_image.url if getattr(campaign, "banner_image", None) else ""),
            },
        }
    )


@login_required
@require_http_methods(["GET"])
def api_festival_sales(request):
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
        return JsonResponse({"detail": "No festival campaign found"}, status=404)

    invoices = (
        Invoice.objects.select_related("order", "order__party")
        .filter(order__owner=owner, order__order_type="SALE", order__festival_campaign=campaign)
        .order_by("-created_at", "-id")
    )
    total_sales = invoices.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
    total_discount = (
        Order.objects.filter(owner=owner, order_type="SALE", festival_campaign=campaign).aggregate(t=Sum("festival_discount_amount"))["t"]
        or Decimal("0.00")
    )

    daily = (
        invoices.values("created_at__date")
        .annotate(t=Sum("amount"))
        .order_by("created_at__date")
    )
    labels = []
    values = []
    for r in daily:
        d = r.get("created_at__date")
        if not d:
            continue
        labels.append(d.strftime("%d %b"))
        values.append(str((r.get("t") or Decimal("0.00")).quantize(Decimal("0.01"))))

    return JsonResponse(
        {
            "campaign": {"id": campaign.id, "name": campaign.name},
            "total_sales": str(total_sales.quantize(Decimal("0.01"))),
            "total_discount": str(total_discount.quantize(Decimal("0.01"))),
            "invoice_count": invoices.count(),
            "chart": {"labels": labels, "values": values},
            "invoices": [
                {
                    "id": inv.id,
                    "number": inv.number,
                    "customer": inv.order.party.name if inv.order and inv.order.party else "",
                    "created_at": inv.created_at.isoformat() if inv.created_at else "",
                    "discount": str((inv.order.festival_discount_amount or Decimal("0.00")).quantize(Decimal("0.01"))),
                    "amount": str((inv.amount or Decimal("0.00")).quantize(Decimal("0.01"))),
                }
                for inv in invoices[:50]
            ],
        }
    )
