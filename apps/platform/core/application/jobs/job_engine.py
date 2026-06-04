from celery import current_app

from apps.platform.core.models import BackgroundJobDefinition


class BackgroundJobEngine:
    def enqueue(self, key, payload=None, tenant=None, countdown=None):
        job = BackgroundJobDefinition.objects.filter(key=key, is_active=True, tenant=tenant).first()
        if not job:
            job = BackgroundJobDefinition.objects.filter(key=key, is_active=True, tenant__isnull=True).first()
        if not job:
            return {"queued": False, "reason": "job_not_found", "key": key}
        options = {"queue": job.queue}
        if countdown is not None:
            options["countdown"] = countdown
        task = current_app.send_task(job.task_path, kwargs={"payload": payload or {}, "tenant_id": str(tenant.id) if tenant else None}, **options)
        return {"queued": True, "task_id": task.id, "queue": job.queue, "job": job.key}

