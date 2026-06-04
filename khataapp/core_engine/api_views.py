from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from khataapp.core_engine.models.logs import RewardLedgerEntry
from khataapp.core_engine.services.analytics_service import update_engine_snapshot
from khataapp.core_engine.services.daily_tasks import complete_task


@login_required
@require_GET
def api_summary(request):
    snap = update_engine_snapshot(request.user)
    return JsonResponse(snap.payload, status=200)


@login_required
@require_GET
def api_rewards(request):
    rows = (
        RewardLedgerEntry.objects.filter(owner=request.user)
        .order_by("-created_at", "-id")
        .values("id", "source", "coins_delta", "points_delta", "amount_reference", "created_at")[:200]
    )
    return JsonResponse({"results": list(rows)}, status=200)


@login_required
@require_POST
def api_complete_task(request):
    task_key = (request.POST.get("task_key") or "").strip()
    ok = complete_task(owner=request.user, task_key=task_key, actor=request.user)
    return JsonResponse({"ok": bool(ok), "task_key": task_key}, status=200 if ok else 400)

