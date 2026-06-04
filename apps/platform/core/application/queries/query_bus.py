from django.apps import apps
from django.core.cache import cache

from apps.platform.core.domain.queries import Query
from apps.platform.core.models import QueryDefinition
from apps.platform.identity.application.services.permission_service import PermissionService
from apps.platform.identity.models import Tenant


class QueryBus:
    def __init__(self, permission_service=None):
        self.permission_service = permission_service or PermissionService()

    def execute(self, query: Query, user=None):
        tenant = Tenant.objects.filter(id=query.tenant_id).first() if query.tenant_id else None
        definition = QueryDefinition.objects.filter(key=query.query_key, is_active=True).filter(tenant=tenant).first()
        if not definition:
            definition = QueryDefinition.objects.filter(key=query.query_key, tenant__isnull=True, is_active=True).first()
        if not definition:
            return {"rows": [], "count": 0, "query": query.query_key}
        if definition.permission_key and user:
            if not self.permission_service.has_permission(user, definition.permission_key, tenant=tenant).allowed:
                return {"rows": [], "count": 0, "denied": True}
        cache_key = f"core_query:{tenant.id if tenant else 'global'}:{definition.key}:{hash(str(query.filters))}"
        if definition.cache_seconds:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        result = self._execute_read_model(definition, query.filters)
        if definition.cache_seconds:
            cache.set(cache_key, result, definition.cache_seconds)
        return result

    def _execute_read_model(self, definition, filters):
        source = definition.source or {}
        model_path = source.get("model")
        if not model_path or "." not in model_path:
            return {"rows": [], "count": 0}
        app_label, model_name = model_path.split(".", 1)
        model = apps.get_model(app_label, model_name)
        qs = model.objects.all()
        allowed_filters = set(source.get("allowed_filters") or [])
        for key, value in filters.items():
            if key in allowed_filters:
                qs = qs.filter(**{key: value})
        limit = min(int(source.get("limit") or 100), 500)
        fields = definition.projection or ["id"]
        rows = list(qs.values(*fields)[:limit])
        return {"rows": rows, "count": len(rows), "query": definition.key}

