from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry
from validation.models import FraudAlert

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


def _ref_url(alert: FraudAlert) -> str:
    try:
        if alert.reference_type == "commerce.Invoice":
            return reverse("commerce:invoice_view", kwargs={"invoice_id": alert.reference_id})
        if alert.reference_type == "khataapp.Transaction":
            return reverse("khataapp:transaction_view", kwargs={"id": alert.reference_id})
        if alert.reference_type == "accounts.Expense":
            return reverse("accounts:expense_list")
    except Exception:
        return ""
    return ""


@login_required
def smart_alerts_dashboard(request):
    if not bool(_get_global_setting("ai_tools_enabled", True)) or not bool(_get_global_setting("smart_alerts_enabled", True)):
        return render(request, "validation/disabled.html", {})
    qs = FraudAlert.objects.filter(owner=request.user).order_by("-created_at")
    status = (request.GET.get("status") or "open").strip().lower()
    if status in {"open", "resolved", "ignored"}:
        qs = qs.filter(status=status)

    alerts = list(qs[:200])
    for a in alerts:
        a.ref_url = _ref_url(a)  # type: ignore[attr-defined]

    counts = {
        "open": FraudAlert.objects.filter(owner=request.user, status=FraudAlert.Status.OPEN).count(),
        "resolved": FraudAlert.objects.filter(owner=request.user, status=FraudAlert.Status.RESOLVED).count(),
        "ignored": FraudAlert.objects.filter(owner=request.user, status=FraudAlert.Status.IGNORED).count(),
    }

    return render(request, "validation/dashboard.html", {"alerts": alerts, "counts": counts, "active_status": status})


@login_required
@require_POST
def smart_alert_action(request, alert_id: int, action: str):
    if not bool(_get_global_setting("ai_tools_enabled", True)) or not bool(_get_global_setting("smart_alerts_enabled", True)):
        messages.error(request, "Smart Alerts are disabled by admin settings.")
        return redirect("accounts:dashboard")
    alert = get_object_or_404(FraudAlert, id=alert_id, owner=request.user)
    action = (action or "").strip().lower()
    if action == "resolve":
        alert.mark_resolved(by_user=request.user)
        messages.success(request, "Alert resolved.")
    elif action == "ignore":
        alert.status = FraudAlert.Status.IGNORED
        alert.save(update_fields=["status"])
        messages.info(request, "Alert ignored.")
    else:
        messages.error(request, "Invalid action.")
    return redirect(reverse("validation:dashboard") + f"?status={request.GET.get('status') or 'open'}")
