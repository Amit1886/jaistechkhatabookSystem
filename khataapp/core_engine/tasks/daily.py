from __future__ import annotations

from celery import shared_task

from khataapp.core_engine.models.engine import BusinessGrowthEngine
from khataapp.core_engine.services.analytics_service import update_engine_snapshot
from khataapp.core_engine.services.daily_tasks import ensure_default_tasks


@shared_task(name="khataapp.tasks.update_engine_snapshots_daily")
def update_engine_snapshots_daily():
    """
    Daily snapshot refresh for dashboards.

    Safe to run multiple times; it only updates per-owner cached JSON snapshots.
    """
    ensure_default_tasks()
    owners = (
        BusinessGrowthEngine.objects.select_related("owner")
        .all()
        .only("id", "owner_id")
    )
    updated = 0
    for row in owners:
        if not row.owner_id:
            continue
        update_engine_snapshot(row.owner)
        updated += 1
    return {"updated": updated}

