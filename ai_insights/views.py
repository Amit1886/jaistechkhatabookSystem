from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry
from ai_insights.customer_analyzer import compute_customer_outstanding
from ai_insights.sales_analyzer import (
    compute_profit_summary,
    compute_sales_trend,
    compute_today_sales,
    compute_top_selling_products,
)
from ai_insights.stock_analyzer import compute_low_stock
from ai_insights.stock_analyzer import compute_reorder_suggestions

logger = logging.getLogger(__name__)


def _get_global_setting(key: str, default=""):
    try:
        sync_settings_registry()
    except Exception:
        pass
    try:
        definition = SettingDefinition.objects.filter(key=key).first()
        if not definition:
            return default
        v = SettingValue.objects.filter(definition=definition, owner__isnull=True).first()
        return v.value if v else definition.default_value
    except Exception:
        return default


@login_required
def insights_dashboard(request):
    if not bool(_get_global_setting("ai_tools_enabled", True)) or not bool(_get_global_setting("ai_insights_enabled", True)):
        return render(request, "ai_insights/disabled.html", {})
    owner = request.user
    try:
        today = compute_today_sales(owner)
    except Exception:
        logger.exception("AI insights today sales failed")
        today = None
    try:
        top_products = compute_top_selling_products(owner, limit=5)
    except Exception:
        logger.exception("AI insights top products failed")
        top_products = []
    try:
        low_stock = compute_low_stock(owner, limit=10)
    except Exception:
        logger.exception("AI insights low stock failed")
        low_stock = []
    try:
        reorder = compute_reorder_suggestions(owner, days=30, limit=10)
    except Exception:
        logger.exception("AI insights reorder suggestions failed")
        reorder = []
    try:
        outstanding = compute_customer_outstanding(owner, limit=10)
    except Exception:
        logger.exception("AI insights outstanding failed")
        outstanding = []
    try:
        trend = compute_sales_trend(owner, days=14)
    except Exception:
        logger.exception("AI insights trend failed")
        trend = []
    try:
        profit = compute_profit_summary(owner, days=30)
    except Exception:
        logger.exception("AI insights profit failed")
        profit = {}

    return render(
        request,
        "ai_insights/dashboard.html",
        {
            "today": today,
            "top_products": top_products,
            "low_stock": low_stock,
            "reorder": reorder,
            "outstanding": outstanding,
            "trend": trend,
            "profit": profit,
        },
    )
