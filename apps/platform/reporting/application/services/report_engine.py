import time

from django.db.models import Sum

from apps.platform.identity.application.services.permission_service import PermissionService
from apps.platform.reporting.application.services.filter_engine import ReportFilterEngine
from apps.platform.reporting.infrastructure.repositories.report_repository import ReportRepository


class ReportEngine:
    def __init__(self, repository=None, filter_engine=None, permission_service=None):
        self.repository = repository or ReportRepository()
        self.filter_engine = filter_engine or ReportFilterEngine()
        self.permission_service = permission_service or PermissionService()

    def run(self, key, raw_filters=None, tenant=None, user=None, page=1, page_size=50):
        started = time.perf_counter()
        template = self.repository.template_by_key(key, tenant=tenant)
        if not template:
            return {"error": "report_not_found", "rows": [], "count": 0}
        if template.permission_key and user:
            decision = self.permission_service.has_permission(user, template.permission_key, tenant=tenant)
            if not decision.allowed:
                return {"error": "permission_denied", "rows": [], "count": 0}
        filters = self.filter_engine.normalize(raw_filters or {})
        cache_key = f"report:{tenant.id if tenant else 'global'}:{template.key}:{hash(str(filters))}:{page}:{page_size}"
        if template.cache_seconds:
            cached = self.repository.cache_get(cache_key)
            if cached is not None:
                return cached
        qs = self.repository.model_queryset(template.source_model)
        qs = self.filter_engine.apply(qs, template, filters)
        qs = self._apply_tenant(qs, tenant)
        total_count = qs.count()
        columns = template.columns or ["id"]
        start = max(int(page) - 1, 0) * int(page_size)
        end = start + int(page_size)
        rows = list(qs.values(*columns)[start:end])
        result = {
            "key": template.key,
            "name": template.name,
            "domain": template.domain,
            "type": template.report_type,
            "columns": columns,
            "filters": filters,
            "rows": rows,
            "count": total_count,
            "page": int(page),
            "page_size": int(page_size),
            "has_next": end < total_count,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "summary": self._summary(qs, template),
            "chart": self._chart(qs, template),
        }
        run = self.repository.create_run(tenant=tenant, template=template, user=user if getattr(user, "is_authenticated", False) else None, filters=filters)
        run.status = "success"
        run.row_count = total_count
        run.duration_ms = result["duration_ms"]
        run.result_preview = {"rows": rows[:10], "summary": result["summary"]}
        run.save(update_fields=["status", "row_count", "duration_ms", "result_preview", "updated_at"])
        result["run_id"] = str(run.id)
        if template.cache_seconds:
            self.repository.cache_set(cache_key, result, template.cache_seconds)
        return result

    def _apply_tenant(self, qs, tenant):
        if tenant is not None and any(field.name == "tenant" for field in qs.model._meta.fields):
            return qs.filter(tenant=tenant)
        return qs

    def _summary(self, qs, template):
        aggregations = (template.query_spec or {}).get("summary", {})
        result = {}
        for key, field in aggregations.items():
            result[key] = qs.aggregate(value=Sum(field)).get("value") or 0
        return result

    def _chart(self, qs, template):
        spec = template.chart_spec or {}
        group_by = spec.get("group_by")
        value = spec.get("value")
        if not group_by or not value:
            return {"labels": [], "datasets": []}
        rows = list(qs.values(group_by).annotate(value=Sum(value)).order_by(group_by)[:100])
        return {
            "labels": [str(row[group_by]) for row in rows],
            "datasets": [{"label": template.name, "data": [float(row["value"] or 0) for row in rows]}],
        }

