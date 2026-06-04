from __future__ import annotations

import json
import time
from typing import Iterable

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.db import transaction
from django.test import Client
from django.utils import timezone

from channels.layers import get_channel_layer

from saas.models import PermissionNode, RoleTemplate, RoleTemplatePermission, UserPermissionGraph, UserPermissionOverride
from saas.utils.apgs import apgs_has_permission

from .models import (
    AuditLog,
    APITestLog,
    APIRegistry,
    AppFeatureMapping,
    DashboardWidget,
    DeviceSession,
    DynamicButton,
    DynamicMenuItem,
    DynamicModule,
    EnterpriseSetting,
    PermissionTemplate,
    ThemeConfig,
    UserWorkspace,
    Workspace,
)


PLATFORM_PERMISSION_KEYS = ("web_access", "app_access", "pos_access", "kiosk_access", "api_access")
ACTION_KEYS = ("view", "create", "edit", "delete", "export", "print", "approve")


def user_can(user, key: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        if apgs_has_permission(user, key):
            return True
    except Exception:
        pass
    has_permission = getattr(user, "has_permission", None)
    if callable(has_permission):
        try:
            return bool(has_permission(key))
        except Exception:
            return False
    return False


def visible_modules_for_user(user, platform: str = "web"):
    modules = DynamicModule.objects.filter(is_enabled=True).order_by("order", "name")
    visible = []
    for module in modules:
        platforms = module.access_platforms or []
        if platforms and platform not in platforms:
            continue
        required = module.required_permissions or []
        if required and not any(user_can(user, key) for key in required):
            continue
        visible.append(module)
    return visible


def get_workspace_for_user(user, platform: str = "web") -> Workspace | None:
    explicit = getattr(user, "enterprise_workspace", None)
    if explicit and explicit.workspace and explicit.workspace.is_active:
        return explicit.workspace
    role_key = (getattr(user, "primary_role", "") or getattr(user, "role", "") or "").strip().lower()
    if role_key:
        workspace = Workspace.objects.filter(role__key=role_key, platform__in=[platform, "", "web"], is_active=True).order_by("-platform", "order").first()
        if workspace:
            return workspace
    return Workspace.objects.filter(is_default=True, is_active=True).order_by("order").first()


def theme_payload(platform: str = "web") -> dict:
    theme = ThemeConfig.objects.filter(is_active=True).order_by("-is_default", "name").first()
    if not theme:
        return {
            "brand_name": "Billentra",
            "primary": "#0F766E",
            "secondary": "#2563EB",
            "accent": "#F59E0B",
            "surface": "#F8FAFC",
            "dark_surface": "#0B1120",
            "radius": 8,
            "density": "comfortable",
        }
    payload = {
        "key": theme.key,
        "brand_name": theme.brand_name,
        "logo_url": theme.logo_url,
        "primary": theme.primary,
        "secondary": theme.secondary,
        "accent": theme.accent,
        "surface": theme.surface,
        "dark_surface": theme.dark_surface,
        "radius": theme.radius,
        "density": theme.density,
        "typography": theme.typography,
    }
    payload.update((theme.platform_overrides or {}).get(platform, {}))
    return payload


def bootstrap_payload(user, request=None, platform: str = "web") -> dict:
    workspace = get_workspace_for_user(user, platform=platform)
    modules = visible_modules_for_user(user, platform=platform)
    widgets_qs = DashboardWidget.objects.filter(is_enabled=True)
    if workspace:
        widgets_qs = widgets_qs.filter(workspace__in=[workspace, None])
    widgets = []
    for widget in widgets_qs.select_related("module", "workspace").order_by("order", "title"):
        if widget.permission_key and not user_can(user, widget.permission_key):
            continue
        widgets.append(
            {
                "key": widget.key,
                "title": widget.title,
                "type": widget.widget_type,
                "module": widget.module.key if widget.module else "",
                "permission": widget.permission_key,
                "data_source": widget.data_source,
                "config": widget.config,
                "order": widget.order,
            }
        )
    return {
        "version": "2026.05.enterprise-control",
        "platform": platform,
        "workspace": {
            "key": workspace.key if workspace else "default",
            "name": workspace.name if workspace else "Default Workspace",
            "landing_route": workspace.landing_route if workspace else "/accounts/dashboard/",
            "layout": workspace.layout_schema if workspace else {},
        },
        "theme": theme_payload(platform=platform),
        "modules": [
            {
                "key": m.key,
                "title": m.name,
                "icon": m.icon,
                "color": m.color,
                "web_url": m.web_url,
                "route": m.app_route,
                "api_namespace": m.api_namespace,
                "order": m.order,
                "enabled": m.is_enabled,
                "visible": True,
                "settings": m.settings,
            }
            for m in modules
        ],
        "menu": workspace.menu_schema if workspace and workspace.menu_schema else [
            {"key": m.key, "title": m.name, "icon": m.icon, "route": m.app_route or m.web_url, "color": m.color}
            for m in modules
        ],
        "sidebar": sidebar_tree(user, workspace=workspace, modules=modules, platform=platform),
        "launcher": launcher_payload(user, modules=modules, platform=platform),
        "buttons": button_payload(user, workspace=workspace, platform=platform),
        "widgets": widgets,
        "permissions": permission_matrix(user, modules),
        "realtime": {
            "permission_channel": "ws/enterprise/permissions/",
            "dashboard_channel": "ws/enterprise/dashboard/",
            "module_channel": "ws/enterprise/modules/",
        },
    }


def launcher_payload(user, modules: Iterable[DynamicModule] | None = None, platform: str = "web") -> list[dict]:
    modules = list(modules if modules is not None else visible_modules_for_user(user, platform=platform))
    return [
        {
            "key": module.key,
            "title": module.name,
            "icon": module.icon,
            "color": module.color,
            "route": module.app_route or module.web_url or f"/{module.key}",
            "web_url": module.web_url,
            "api_namespace": module.api_namespace,
            "order": module.order,
            "settings": module.settings,
        }
        for module in modules
    ]


def button_payload(user, workspace: Workspace | None = None, platform: str = "web") -> list[dict]:
    try:
        rows = DynamicButton.objects.filter(is_enabled=True).select_related("module", "workspace").order_by("order", "label")
        if workspace:
            rows = rows.filter(workspace__in=[workspace, None])
        rows = list(rows)
    except Exception:
        rows = []
    buttons = []
    user_role = (getattr(user, "primary_role", "") or getattr(user, "role", "") or getattr(user, "billing_role_type", "") or "").strip().lower()
    plan_key = ""
    try:
        from billing.services import get_effective_plan

        plan = get_effective_plan(user)
        plan_key = ((getattr(plan, "slug", "") or getattr(plan, "name", "") or "") if plan else "").strip().lower()
    except Exception:
        plan_key = ""
    for row in rows:
        if not _platform_allowed(row.platform_access, platform):
            continue
        if row.permission_key and not user_can(user, row.permission_key):
            continue
        role_keys = [str(key).strip().lower() for key in (row.role_keys or []) if str(key).strip()]
        if role_keys and user_role not in role_keys and not getattr(user, "is_superuser", False):
            continue
        plan_keys = [str(key).strip().lower() for key in (row.plan_keys or []) if str(key).strip()]
        if plan_keys and plan_key not in plan_keys and not getattr(user, "is_superuser", False):
            continue
        buttons.append(
            {
                "key": row.key,
                "label": row.label,
                "description": row.description,
                "module": row.module.key if row.module else "",
                "action_type": row.action_type,
                "route": row.route,
                "api_endpoint": row.api_endpoint,
                "service_key": row.service_key,
                "icon": row.icon,
                "color": row.color,
                "gradient": row.gradient,
                "shape": row.shape,
                "animation": row.animation,
                "permission": row.permission_key,
                "plans": row.plan_keys,
                "roles": row.role_keys,
                "primary": row.is_primary,
                "order": row.order,
                "config": row.config,
            }
        )
    if buttons:
        return buttons
    return [
        {
            "key": module.key,
            "label": module.name,
            "module": module.key,
            "action_type": "module",
            "route": module.app_route or module.web_url or f"/{module.key}",
            "icon": module.icon,
            "color": module.color,
            "gradient": [module.color, "#0B1120"],
            "shape": "rounded",
            "animation": "smooth",
            "permission": "",
            "plans": [],
            "roles": [],
            "primary": module.order <= 20,
            "order": module.order,
            "config": {"auto_generated": True},
        }
        for module in visible_modules_for_user(user, platform=platform)[:24]
    ]


def sidebar_tree(user, workspace: Workspace | None = None, modules: Iterable[DynamicModule] | None = None, platform: str = "web") -> list[dict]:
    try:
        rows = list(
            DynamicMenuItem.objects.filter(is_enabled=True)
            .select_related("parent", "module", "workspace")
            .order_by("order", "title")
        )
    except Exception:
        rows = []
    if workspace:
        rows = [row for row in rows if row.workspace_id in {workspace.id, None}]
    visible = []
    for row in rows:
        if not _platform_allowed(row.platform_access, platform):
            continue
        if row.permission_key and not user_can(user, row.permission_key):
            continue
        visible.append(row)
    if visible:
        return _menu_tree(visible)
    modules = list(modules if modules is not None else visible_modules_for_user(user, platform=platform))
    return [
        {
            "key": module.key,
            "title": module.name,
            "icon": module.icon,
            "route": module.app_route or module.web_url or f"/{module.key}",
            "badge": "",
            "color": module.color,
            "is_group": False,
            "children": [],
            "order": module.order,
            "config": {"auto_generated": True},
        }
        for module in modules
    ]


def _menu_tree(rows: list[DynamicMenuItem]) -> list[dict]:
    by_parent: dict[int | None, list[DynamicMenuItem]] = {}
    for row in rows:
        by_parent.setdefault(row.parent_id, []).append(row)

    def build(parent_id=None):
        items = []
        for row in by_parent.get(parent_id, []):
            items.append(
                {
                    "key": row.key,
                    "title": row.title,
                    "icon": row.icon,
                    "route": row.route or (row.module.app_route if row.module else ""),
                    "badge": row.badge,
                    "color": row.color,
                    "module": row.module.key if row.module else "",
                    "is_group": row.is_group,
                    "children": build(row.id),
                    "order": row.order,
                    "config": row.config,
                }
            )
        return items

    return build(None)


def _platform_allowed(platforms, platform: str) -> bool:
    return not platforms or platform in platforms


def permission_matrix(user, modules: Iterable[DynamicModule] | None = None) -> dict:
    result: dict[str, dict] = {
        "platform": {key: user_can(user, key) for key in PLATFORM_PERMISSION_KEYS},
    }
    modules = modules if modules is not None else DynamicModule.objects.filter(is_enabled=True)
    for module in modules:
        result[module.key] = {
            action: user_can(user, f"{module.key}_{action}") or user_can(user, f"{action}_{module.key}")
            for action in ACTION_KEYS
        }
    return result


@transaction.atomic
def apply_template_to_user(user, template: PermissionTemplate, *, actor=None) -> UserPermissionGraph:
    role = template.role
    if not role:
        role, _ = RoleTemplate.objects.get_or_create(
            key=template.key,
            defaults={"label": template.name, "is_system": template.is_system, "is_active": True},
        )
        template.role = role
        template.save(update_fields=["role", "updated_at"])
    graph, _ = UserPermissionGraph.objects.update_or_create(
        user=user,
        seller=getattr(user, "seller", None),
        defaults={"role": role, "inherit_from_owner": True, "is_active": True},
    )
    for key in template.permission_keys or []:
        permission = PermissionNode.objects.filter(key=key).first()
        if not permission:
            continue
        UserPermissionOverride.objects.update_or_create(
            user=user,
            seller=getattr(user, "seller", None),
            permission=permission,
            defaults={"effect": UserPermissionOverride.EFFECT_ALLOW, "note": f"template:{template.key}"},
        )
    cache.delete_pattern(f"apgs:permset:u{user.id}:*") if hasattr(cache, "delete_pattern") else None
    audit(actor, "permission_template.apply", target=f"user:{user.pk}", metadata={"template": template.key})
    broadcast_enterprise_event("permissions", {"type": "permissions.updated", "user_id": user.pk, "template": template.key})
    return graph


def register_device(request, device_id: str, platform: str = "", app_version: str = ""):
    if not device_id or not getattr(request.user, "is_authenticated", False):
        return None
    ip = _client_ip(request)
    session, _ = DeviceSession.objects.update_or_create(
        user=request.user,
        device_id=device_id[:120],
        defaults={
            "platform": platform[:30],
            "app_version": app_version[:40],
            "ip_address": ip or None,
            "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:2000],
            "is_active": True,
        },
    )
    return session


def audit(actor, action: str, *, request=None, target: str = "", platform: str = "", metadata: dict | None = None):
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target=target,
        platform=platform,
        ip_address=_client_ip(request) if request else None,
        metadata=metadata or {},
    )


def broadcast_enterprise_event(stream: str, payload: dict):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"enterprise_{stream}",
        {"type": "enterprise.broadcast", "payload": payload},
    )


def _client_ip(request) -> str:
    if not request:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def public_settings_payload(platform: str = "app") -> dict:
    rows = EnterpriseSetting.objects.filter(is_active=True, is_public=True)
    payload = {}
    for row in rows:
        platforms = row.platform_access or []
        if platforms and platform not in platforms:
            continue
        payload[row.key] = "***" if row.is_secret else row.value
    return payload


def central_app_config(user=None, *, platform: str = "app", request=None) -> dict:
    from fastapi_app.routers import mobile as fastapi_mobile

    if user and getattr(user, "is_authenticated", False):
        payload = fastapi_mobile.bootstrap(platform=platform, user=user)
    else:
        theme = theme_payload(platform=platform)
        payload = {
            "version": "2026.05.public-system-config",
            "platform": platform,
            "app_name": theme.get("brand_name") or "Billentra",
            "theme": theme,
            "branding": theme,
            "modules": [],
            "features": {},
            "permissions": {},
            "menu": [],
            "buttons": [],
        }
    public_settings = public_settings_payload(platform=platform)
    api_base_url = _setting_value("api_base_url", request=request) or _request_base_url(request)
    payload.update(
        {
            "app_name": payload.get("app_name") or payload.get("theme", {}).get("brand_name", "Billentra"),
            "api_base_url": api_base_url,
            "backend_url": _setting_value("backend_url", request=request) or _request_base_url(request),
            "settings": public_settings,
            "admin_controlled": True,
            "manual_client_settings": False,
        }
    )
    return payload


def _setting_value(key: str, *, request=None):
    setting = EnterpriseSetting.objects.filter(key=key, is_active=True).first()
    if not setting:
        return ""
    value = setting.value
    if isinstance(value, dict):
        return value.get("value") or value.get("url") or value.get("text") or ""
    return value


def _request_base_url(request=None) -> str:
    if not request:
        return ""
    return request.build_absolute_uri("/").rstrip("/")


def sync_fastapi_routes(*, actor=None) -> dict:
    from fastapi_app.main import app

    created = 0
    updated = 0
    seen = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = sorted([m for m in getattr(route, "methods", set()) if m not in {"HEAD", "OPTIONS"}])
        if not path or not methods:
            continue
        module = _module_from_endpoint(path)
        for method in methods:
            endpoint = f"/fastapi{path}"
            seen.add((endpoint, method))
            obj, was_created = APIRegistry.objects.update_or_create(
                endpoint=endpoint,
                method=method,
                defaults={
                    "name": _api_name(method, endpoint),
                    "module": module,
                    "status": APIRegistry.STATUS_ACTIVE,
                    "source": "fastapi",
                    "connected_apps": _apps_from_endpoint(endpoint),
                    "permission_keys": _permissions_from_endpoint(endpoint),
                    "version": "v1",
                    "auth_required": "auth/login" not in endpoint and "openapi" not in endpoint and "docs" not in endpoint,
                    "is_active": True,
                },
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1
    APIRegistry.objects.filter(source="fastapi").exclude(endpoint__in=[x[0] for x in seen]).update(status=APIRegistry.STATUS_MISSING, is_active=False)
    if actor:
        audit(actor, "api_registry.sync_fastapi", target="fastapi", metadata={"created": created, "updated": updated})
    return {"created": created, "updated": updated, "total": len(seen)}


def test_registered_api(api: APIRegistry, *, actor=None, payload: dict | None = None, headers: dict | None = None) -> APITestLog:
    started = time.perf_counter()
    status_code = 0
    response_payload = {}
    response_text = ""
    error = ""
    auth_status = "not_required" if not api.auth_required else "required"
    request_payload = payload or {}
    request_headers = headers or {}
    if api.auth_required and actor and getattr(actor, "is_authenticated", False) and not any(k.lower() == "authorization" for k in request_headers):
        try:
            from fastapi_app.auth.token_utils import create_access_token

            request_headers["Authorization"] = f"Bearer {create_access_token(user=actor)}"
            auth_status = "jwt_attached"
        except Exception:
            auth_status = "required"
    try:
        path = api.endpoint
        if path.startswith("/fastapi/"):
            from fastapi.testclient import TestClient
            from fastapi_app.main import app

            client = TestClient(app)
            response = client.request(api.method, path.replace("/fastapi", "", 1), json=request_payload or None, headers=request_headers)
            status_code = response.status_code
            response_text = response.text[:10000]
            try:
                response_payload = response.json()
            except Exception:
                response_payload = {}
        else:
            client = Client()
            method = api.method.lower()
            func = getattr(client, method)
            response = func(path, data=json.dumps(request_payload), content_type="application/json", **_django_headers(request_headers))
            status_code = response.status_code
            response_text = response.content.decode("utf-8", errors="ignore")[:10000]
            try:
                response_payload = json.loads(response_text)
            except Exception:
                response_payload = {}
    except Exception as exc:
        error = str(exc)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    ok = 200 <= status_code < 500 and not error
    api.last_usage_at = timezone.now()
    api.last_response_status = status_code
    api.last_response_time_ms = elapsed_ms
    api.last_error = error
    api.status = APIRegistry.STATUS_TESTED if ok else APIRegistry.STATUS_FAILED
    api.save(update_fields=["last_usage_at", "last_response_status", "last_response_time_ms", "last_error", "status", "updated_at"])
    log = APITestLog.objects.create(
        api=api,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        request_payload=request_payload,
        request_headers=request_headers,
        response_payload=response_payload,
        response_text=response_text,
        status_code=status_code,
        response_time_ms=elapsed_ms,
        auth_status=auth_status,
        error=error,
    )
    return log


def refresh_feature_mapping_status(*, actor=None) -> dict:
    updated = 0
    for mapping in AppFeatureMapping.objects.prefetch_related("connected_apis").all():
        required = [str(item).strip() for item in (mapping.required_apis or []) if str(item).strip()]
        connected = set(mapping.connected_apis.values_list("endpoint", flat=True))
        active = set(APIRegistry.objects.filter(endpoint__in=required, status__in=[APIRegistry.STATUS_ACTIVE, APIRegistry.STATUS_TESTED, APIRegistry.STATUS_CONNECTED]).values_list("endpoint", flat=True))
        if required and active == set(required):
            status = "active"
        elif required and (active or connected):
            status = "partial"
        elif required:
            status = "missing"
        else:
            status = "pending"
        mapping.status = status
        mapping.last_checked_at = timezone.now()
        mapping.save(update_fields=["status", "last_checked_at", "updated_at"])
        updated += 1
    if actor:
        audit(actor, "feature_mapping.refresh_status", target="app_features", metadata={"updated": updated})
    return {"updated": updated}


def _module_from_endpoint(endpoint: str) -> str:
    parts = [part for part in endpoint.strip("/").split("/") if part not in {"fastapi", "api", "v1"}]
    return parts[0] if parts else "system"


def _api_name(method: str, endpoint: str) -> str:
    return f"{method} {endpoint}".replace("_", " ").title()


def _apps_from_endpoint(endpoint: str) -> list[str]:
    apps = ["web"]
    if "/mobile/" in endpoint or "/offline" in endpoint:
        apps.append("mobile")
    if "/pos" in endpoint:
        apps.append("pos")
    if "kiosk" in endpoint or "self-checkout" in endpoint:
        apps.append("kiosk")
    return sorted(set(apps))


def _permissions_from_endpoint(endpoint: str) -> list[str]:
    module = _module_from_endpoint(endpoint)
    return [f"{module}_view", f"view_{module}"]


def _django_headers(headers: dict) -> dict:
    result = {}
    for key, value in headers.items():
        header = "HTTP_" + key.upper().replace("-", "_")
        if key.lower() == "content-type":
            continue
        result[header] = value
    return result
