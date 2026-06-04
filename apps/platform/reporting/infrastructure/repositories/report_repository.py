from django.apps import apps
from django.core.cache import cache
from django.db.models import Q

from apps.platform.reporting.models import ReportRun, ReportTemplate


class ReportRepository:
    def template_by_key(self, key, tenant=None):
        qs = ReportTemplate.objects.filter(key=key, is_active=True)
        return qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True)).order_by("-tenant_id").first()

    def model_queryset(self, model_path):
        app_label, model_name = model_path.split(".", 1)
        return apps.get_model(app_label, model_name).objects.all()

    def cache_get(self, key):
        return cache.get(key)

    def cache_set(self, key, value, seconds):
        cache.set(key, value, seconds)

    def create_run(self, *, tenant, template, user, filters):
        return ReportRun.objects.create(tenant=tenant, template=template, user=user, filters=filters)

