from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from khataapp.core_engine.admin_panels.forms import EngineControlPanelSettingsForm
from khataapp.core_engine.models.engine import BusinessGrowthEngine
from khataapp.core_engine.models.logs import EngineEventLog, RewardLedgerEntry
from khataapp.core_engine.models.referral import ReferralRecord
from khataapp.core_engine.models.settings import EngineControlPanelSettings


def _is_staff(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


@login_required
@user_passes_test(_is_staff)
def control_center(request):
    settings_obj = EngineControlPanelSettings.get_solo()
    if request.method == "POST":
        form = EngineControlPanelSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Central Engine settings updated.")
            return redirect("central_engine:admin_control_center")
    else:
        form = EngineControlPanelSettingsForm(instance=settings_obj)

    stats = {
        "engines": BusinessGrowthEngine.objects.count(),
        "reward_entries": RewardLedgerEntry.objects.count(),
        "referrals": ReferralRecord.objects.count(),
        "logs": EngineEventLog.objects.count(),
    }

    return render(
        request,
        "central_engine/admin/control_center.html",
        {
            "form": form,
            "settings_obj": settings_obj,
            "stats": stats,
        },
    )


@login_required
@user_passes_test(_is_staff)
def logs_audit(request):
    owner_id_raw = (request.GET.get("owner_id") or "").strip()
    qs = EngineEventLog.objects.select_related("owner", "actor").all().order_by("-created_at", "-id")
    if owner_id_raw:
        try:
            owner_id = int(owner_id_raw)
        except Exception:
            owner_id = None
        if owner_id:
            qs = qs.filter(owner_id=owner_id)
    logs = qs[:300]
    return render(
        request,
        "central_engine/admin/logs_audit.html",
        {
            "logs": logs,
            "owner_id": owner_id_raw,
        },
    )

