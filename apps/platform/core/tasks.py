from celery import shared_task

from apps.platform.core.application.event_handlers.enterprise_handlers import EnterpriseEventHandler
from apps.platform.identity.models import Tenant


@shared_task(bind=True, max_retries=3)
def process_enterprise_event(self, event_type, payload=None, tenant_id=None, user_id=None):
    tenant = Tenant.objects.filter(id=tenant_id).first() if tenant_id else None
    user = None
    if user_id:
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.filter(id=user_id).first()
    return EnterpriseEventHandler().handle(event_type, payload or {}, tenant=tenant, user=user)


@shared_task(bind=True, max_retries=3)
def run_background_job(self, payload=None, tenant_id=None):
    return {"ok": True, "tenant_id": tenant_id, "payload": payload or {}}

