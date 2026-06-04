from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from smart_bi.services.business_health import upsert_business_metric


@shared_task
def update_business_metrics_daily() -> dict:
    """
    Daily scheduled job to refresh BusinessMetric rows for all active users.

    Note: In desktop/dev mode without Celery Beat, metrics are also refreshed lazily
    when the dashboard is viewed.
    """
    day = timezone.localdate()
    User = get_user_model()
    updated = 0
    for u in User.objects.filter(is_active=True).only("id").iterator():
        try:
            upsert_business_metric(u, day=day)
            updated += 1
        except Exception:
            continue
    return {"date": str(day), "updated_users": updated}

