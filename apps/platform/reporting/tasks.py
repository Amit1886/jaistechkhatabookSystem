from celery import shared_task

from apps.platform.identity.models import Tenant
from apps.platform.reporting.application.services.analytics_engine import AnalyticsEngine


@shared_task(bind=True, max_retries=3)
def refresh_reporting_metrics(self, tenant_id=None):
    tenant = Tenant.objects.filter(id=tenant_id).first() if tenant_id else None
    return {"kpis": AnalyticsEngine().kpis(tenant)}

