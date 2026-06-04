from apps.platform.core.infrastructure.repositories.core_repository import CoreRepository, DB_NOT_READY
from apps.platform.identity.application.services.permission_service import PermissionService


class MetadataService:
    def __init__(self, repository=None, permission_service=None):
        self.repository = repository or CoreRepository()
        self.permission_service = permission_service or PermissionService()

    def modules_for_user(self, user, tenant=None):
        try:
            modules = []
            for module in self.repository.active_modules(tenant):
                permission_key = module.settings.get("permission_key") if isinstance(module.settings, dict) else ""
                if permission_key and not self.permission_service.has_permission(user, permission_key, tenant=tenant).allowed:
                    continue
                modules.append(module)
            return modules
        except DB_NOT_READY:
            return []

    def sidebar_for_user(self, user, tenant=None):
        try:
            items = []
            for item in self.repository.visible_menu_items(tenant):
                if item.permission_key and not self.permission_service.has_permission(user, item.permission_key, tenant=tenant).allowed:
                    continue
                items.append(
                    {
                        "id": str(item.id),
                        "key": item.key,
                        "label": item.label,
                        "icon": item.icon,
                        "url": item.url,
                        "route_name": item.route_name,
                        "parent_id": str(item.parent_id) if item.parent_id else None,
                        "sort_order": item.sort_order,
                        "module": item.module.key if item.module_id else "",
                    }
                )
            return self._tree(items)
        except DB_NOT_READY:
            return []

    def form_schema(self, key, user, tenant=None):
        form = self.repository.form_by_key(key, tenant)
        if not form:
            return None
        fields = []
        for field in form.fields.filter(is_active=True).order_by("sort_order", "label"):
            if field.permission_key and not self.permission_service.has_permission(user, field.permission_key, tenant=tenant).allowed:
                continue
            fields.append(
                {
                    "key": field.key,
                    "label": field.label,
                    "type": field.field_type,
                    "required": field.is_required,
                    "data_source": field.data_source,
                    "default_value": field.default_value,
                    "validation": field.validation_rules,
                    "metadata": field.metadata,
                }
            )
        return {
            "key": form.key,
            "name": form.name,
            "module": form.module.key,
            "layout": form.layout,
            "validation_schema": form.validation_schema,
            "version": form.version,
            "fields": fields,
        }

    def is_feature_enabled(self, key, tenant=None):
        toggle = self.repository.feature_toggle(key, tenant)
        return True if toggle is None else toggle.is_enabled_now()

    def _tree(self, items):
        by_id = {item["id"]: {**item, "children": []} for item in items}
        roots = []
        for item in by_id.values():
            parent_id = item.pop("parent_id")
            if parent_id and parent_id in by_id:
                by_id[parent_id]["children"].append(item)
            else:
                roots.append(item)
        return roots
