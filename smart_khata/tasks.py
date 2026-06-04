from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from smart_khata.services.reminders import send_due_reminders_for_owner


@shared_task
def send_khata_due_reminders(owner_id: int | None = None, dry_run: bool = False, limit: int = 200):
    """
    Optional Celery task wrapper for Smart Khata reminders.

    Desktop builds typically disable Celery; use the management command there.
    """
    User = get_user_model()
    qs = User.objects.filter(is_active=True)
    if owner_id:
        qs = qs.filter(id=int(owner_id))
    results = []
    for owner in qs.iterator(chunk_size=200):
        results.append(send_due_reminders_for_owner(owner, dry_run=dry_run, limit=limit))
    return {"owners": qs.count(), "results": results}

