from django.contrib.auth.models import Permission
from fastapi import APIRouter, Depends, HTTPException

from core.metadata.scanner import resolve_model, scan_models, model_metadata
from core.settings_engine.service import settings_service
from enterprise_control.services import (
    bootstrap_payload,
    button_payload,
    get_workspace_for_user,
    permission_matrix,
    sidebar_tree,
    theme_payload,
    user_can,
    visible_modules_for_user,
)
from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/mobile", tags=["flutter-dynamic-ui"])


@router.get("/bootstrap")
def bootstrap(platform: str = "app", user=Depends(current_access_user)):
    payload = bootstrap_payload(user, platform=platform)
    module_rows = modules(platform=platform, user=user)["results"]
    permission_rows = payload.get("permissions") or {}
    _ensure_module_permissions(permission_rows, module_rows, user=user)
    payload.update(
        {
            "modules": module_rows,
            "menu": menu(platform=platform, user=user)["results"],
            "sidebar": sidebar_tree(user, platform=platform),
            "launcher": [
                {
                    "key": row["key"],
                    "title": row.get("title") or row.get("name") or row["key"].title(),
                    "icon": row.get("icon", "apps"),
                    "route": row.get("route") or f"/{row['key']}",
                    "color": row.get("color", "#2563EB"),
                    "order": row.get("order", 999),
                }
                for row in module_rows
            ],
            "buttons": dashboard_buttons(platform=platform, user=user)["results"],
            "features": _enabled_features(user),
            "permissions": permission_rows,
            "api": {
                "current_user": "/fastapi/mobile/current-user/",
                "app_config": "/fastapi/mobile/app-config/",
                "modules": "/fastapi/mobile/modules/",
                "menu": "/fastapi/mobile/menu/",
                "dashboard_buttons": "/fastapi/mobile/dashboard-buttons/",
                "metadata": "/fastapi/mobile/screen-metadata/{module}/",
                "crud": "/fastapi/crud/{model_key}",
            },
            "modes": ["app", "mobile", "tablet", "desktop", "pos", "self_checkout", "kiosk"],
            "default_mode": platform,
        }
    )
    return payload


@router.get("/current-user/")
def current_user_profile(platform: str = "app", user=Depends(current_access_user)):
    profile = _profile_payload(user)
    enabled_modules = modules(platform=platform, user=user)["results"]
    enabled_features = _enabled_features(user)
    return {
        "user": _user_payload(user),
        "company": profile["company"],
        "business": profile["business"],
        "role": profile["role"],
        "permissions": _all_permission_keys(user),
        "enabled_modules": enabled_modules,
        "enabled_features": enabled_features,
        "subscription_plan": profile["plan"],
        "app_configuration": app_config(platform=platform, user=user),
    }


@router.get("/app-config/")
def app_config(platform: str = "app", user=Depends(current_access_user)):
    workspace = get_workspace_for_user(user, platform=platform)
    theme = theme_payload(platform=platform)
    module_rows = modules(platform=platform, user=user)["results"]
    menu_rows = menu(platform=platform, user=user)["results"]
    button_rows = dashboard_buttons(platform=platform, user=user)["results"]
    permission_rows = permission_matrix(user)
    _ensure_module_permissions(permission_rows, module_rows, user=user)
    return {
        "version": "2026.05.mobile-app-config",
        "platform": platform,
        "default_mode": platform,
        "app_name": theme.get("brand_name") or "Billentra",
        "logo": theme.get("logo_url", ""),
        "branding": theme,
        "colors": {
            "primary": theme.get("primary", "#0F766E"),
            "secondary": theme.get("secondary", "#2563EB"),
            "accent": theme.get("accent", "#F59E0B"),
            "surface": theme.get("surface", "#F8FAFC"),
            "dark_surface": theme.get("dark_surface", "#0B1120"),
        },
        "gradients": {
            "primary": [theme.get("primary", "#0F766E"), theme.get("secondary", "#2563EB")],
            "accent": [theme.get("accent", "#F59E0B"), theme.get("primary", "#0F766E")],
        },
        "theme": theme,
        "workspace": {
            "key": workspace.key if workspace else "default",
            "name": workspace.name if workspace else "Default Workspace",
            "landing_route": workspace.landing_route if workspace else "/dashboard",
            "layout": (workspace.layout_schema if workspace else {}) or {"columns": 4, "density": theme.get("density", "comfortable")},
        },
        "modules": module_rows,
        "menu": menu_rows,
        "sidebar": sidebar_tree(user, workspace=workspace, platform=platform) or menu_rows,
        "launcher": [
            {
                "key": row["key"],
                "title": row.get("title") or row.get("name") or row["key"].title(),
                "icon": row.get("icon", "apps"),
                "route": row.get("route") or f"/{row['key']}",
                "color": row.get("color", "#2563EB"),
                "order": row.get("order", 999),
            }
            for row in module_rows
        ],
        "buttons": button_rows,
        "widgets": [],
        "permissions": permission_rows,
        "api": {
            "current_user": "/fastapi/mobile/current-user/",
            "app_config": "/fastapi/mobile/app-config/",
            "modules": "/fastapi/mobile/modules/",
            "menu": "/fastapi/mobile/menu/",
            "dashboard_buttons": "/fastapi/mobile/dashboard-buttons/",
            "metadata": "/fastapi/mobile/screen-metadata/{module}/",
            "crud": "/fastapi/crud/{model_key}",
        },
        "features": _enabled_features(user),
        "realtime": {
            "permission_channel": "ws/enterprise/permissions/",
            "dashboard_channel": "ws/enterprise/dashboard/",
            "module_channel": "ws/enterprise/modules/",
        },
        "modes": ["app", "mobile", "tablet", "desktop", "pos", "self_checkout", "kiosk"],
        "menu_config": {"platform": platform, "count": len(menu_rows), "results": menu_rows},
        "dashboard_config": {
            "buttons": button_rows,
            "layout": (workspace.layout_schema if workspace else {}) or {"columns": 4, "density": theme.get("density", "comfortable")},
        },
    }


@router.get("/modules/")
def modules(platform: str = "app", user=Depends(current_access_user)):
    rows = []
    for module in visible_modules_for_user(user, platform=platform):
        rows.append(
            {
                "key": module.key,
                "name": module.name,
                "title": module.name,
                "icon": module.icon or "apps",
                "color": module.color or "#2563EB",
                "route": module.app_route or module.web_url or f"/{module.key}",
                "web_url": module.web_url,
                "api_namespace": module.api_namespace,
                "permission": module.key,
                "visible": True,
                "enabled": module.is_enabled,
                "order": module.order,
                "settings": module.settings or {},
            }
        )
    if not rows:
        rows = _fallback_modules(user)
    permission_rows = permission_matrix(user)
    _ensure_module_permissions(permission_rows, rows, user=user)
    return {"platform": platform, "count": len(rows), "results": rows, "permissions": permission_rows}


@router.get("/dashboard-buttons/")
def dashboard_buttons(platform: str = "app", user=Depends(current_access_user)):
    buttons = button_payload(user, workspace=get_workspace_for_user(user, platform=platform), platform=platform)
    if not buttons:
        buttons = [
            {
                "key": row["key"],
                "label": row["title"],
                "module": row["key"],
                "action_type": "module",
                "route": row["route"],
                "icon": row["icon"],
                "color": row["color"],
                "gradient": [row["color"], "#0B1120"],
                "shape": "rounded",
                "animation": "smooth",
                "permission": "",
                "plans": [],
                "roles": [],
                "primary": row["order"] <= 4,
                "order": row["order"],
                "config": {"auto_generated": True},
            }
            for row in _fallback_modules(user)[:24]
        ]
    return {"platform": platform, "count": len(buttons), "results": buttons}


@router.get("/menu/")
def menu(platform: str = "app", user=Depends(current_access_user)):
    sidebar = sidebar_tree(user, workspace=get_workspace_for_user(user, platform=platform), platform=platform)
    if not sidebar:
        sidebar = [
            {
                "key": row["key"],
                "title": row["title"],
                "icon": row["icon"],
                "route": row["route"],
                "badge": "",
                "color": row["color"],
                "is_group": False,
                "children": [],
                "order": row["order"],
                "config": {"auto_generated": True},
            }
            for row in _fallback_modules(user)
        ]
    return {"platform": platform, "count": len(sidebar), "results": sidebar}


@router.get("/screen-metadata/{module}/")
def screen_metadata(module: str, user=Depends(current_access_user)):
    requested = module.strip().lower()
    if not requested:
        raise HTTPException(status_code=400, detail="missing_module")
    screens = []
    for meta in scan_models():
        model_key = meta["key"].lower()
        if model_key == requested or meta["app_label"].lower() == requested or requested in model_key:
            screens.append(_screen_from_meta(meta))
    if not screens:
        try:
            screens = [_screen_from_meta(model_metadata(resolve_model(module)))]
        except LookupError:
            screens = []
    return {
        "module": module,
        "count": len(screens),
        "screens": screens,
        "fields": screens[0]["form"]["fields"] if screens else [],
        "forms": [screen["form"] for screen in screens],
        "filters": screens[0]["list"]["filters"] if screens else [],
        "table_columns": screens[0]["list"]["columns"] if screens else [],
        "permissions": screens[0]["permissions"] if screens else {},
        "buttons": dashboard_buttons(user=user)["results"],
        "layout": {"type": "list_form", "density": "comfortable"},
    }


@router.get("/screens")
def screens(user=Depends(current_access_user)):
    return {"count": len(scan_models()), "results": [_screen_from_meta(meta) for meta in scan_models()]}


@router.get("/screens/{model_key}")
def screen_detail(model_key: str, user=Depends(current_access_user)):
    try:
        meta = model_metadata(resolve_model(model_key))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _screen_from_meta(meta)


def _screen_from_meta(meta: dict) -> dict:
    fields = [field for field in meta["fields"] if not field["sensitive"]]
    return {
        "key": meta["mobile"]["screen_key"],
        "model": meta["key"],
        "title": meta["label_plural"],
        "list": {
            "endpoint": meta["api"]["list"],
            "columns": [field["name"] for field in fields if not field["read_only"]][:6],
            "search": meta["search_fields"],
            "filters": meta["filter_fields"],
        },
        "form": {
            "endpoint": meta["api"]["base"],
            "fields": [
                {
                    "name": field["name"],
                    "label": field["label"],
                    "widget": field["mobile_widget"],
                    "required": field["required"],
                    "read_only": field["read_only"],
                    "choices": field["choices"],
                    "relation": field["relation"],
                }
                for field in fields
                if not field["read_only"]
            ],
        },
        "permissions": meta["permissions"],
    }


def _user_payload(user) -> dict:
    return {
        "id": str(user.pk),
        "username": getattr(user, "username", "") or "",
        "email": getattr(user, "email", "") or "",
        "mobile": getattr(user, "mobile", "") or "",
        "name": (getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", "") or getattr(user, "email", "")),
        "is_staff": bool(getattr(user, "is_staff", False)),
        "is_superuser": bool(getattr(user, "is_superuser", False)),
    }


def _profile_payload(user) -> dict:
    company = {}
    business = {}
    plan = {}
    role = {
        "key": getattr(user, "primary_role", "") or getattr(user, "role", "") or getattr(user, "billing_role_type", "") or "",
        "label": getattr(user, "primary_role", "") or getattr(user, "role", "") or getattr(user, "billing_role_type", "") or "User",
    }
    profile = None
    for app_label in ("accounts", "khataapp"):
        try:
            from django.apps import apps

            model = apps.get_model(app_label, "UserProfile")
            profile = model.objects.filter(user=user).select_related("plan").first()
            if profile:
                break
        except Exception:
            continue
    if profile:
        business = {
            "name": getattr(profile, "business_name", "") or "Demo Business",
            "type": getattr(profile, "business_type", "") or "",
            "gst_number": getattr(profile, "gst_number", "") or "",
            "address": getattr(profile, "address", "") or "",
        }
        profile_company = getattr(profile, "company", None)
        if profile_company:
            company = {
                "id": str(getattr(profile_company, "pk", "")),
                "name": getattr(profile_company, "company_name", "") or str(profile_company),
                "email": getattr(profile_company, "email", "") or "",
                "mobile": getattr(profile_company, "mobile", "") or "",
            }
    try:
        from billing.services import get_effective_plan

        effective_plan = get_effective_plan(user)
        if effective_plan:
            plan = _plan_payload(effective_plan)
    except Exception:
        pass
    if not plan and profile:
        profile_plan = getattr(profile, "plan", None)
        if profile_plan:
            plan = _plan_payload(profile_plan)
    return {"company": company, "business": business, "plan": plan, "role": role}


def _plan_payload(plan) -> dict:
    return {
        "id": str(getattr(plan, "pk", "")),
        "key": getattr(plan, "slug", "") or str(getattr(plan, "pk", "")),
        "name": getattr(plan, "name", ""),
        "price": str(getattr(plan, "price", "")),
        "price_monthly": str(getattr(plan, "price_monthly", "")),
        "price_yearly": str(getattr(plan, "price_yearly", "")),
        "active": bool(getattr(plan, "active", True)),
    }


def _enabled_features(user) -> dict[str, bool]:
    try:
        from billing.models import FeatureRegistry
        from billing.services import ensure_user_feature_overrides, user_has_feature

        ensure_user_feature_overrides(user)
        return {feature.key: user_has_feature(user, feature.key) for feature in FeatureRegistry.objects.filter(active=True)}
    except Exception:
        return {}


def _all_permission_keys(user) -> list[str]:
    keys = set()
    try:
        keys.update(user.get_all_permissions())
    except Exception:
        pass
    try:
        keys.update(k for k, v in (user.permissions_json or {}).items() if v)
    except Exception:
        pass
    try:
        keys.update(
            Permission.objects.filter(group__user=user).values_list("content_type__app_label", "codename")
        )
    except Exception:
        pass
    normalized = []
    for key in keys:
        if isinstance(key, tuple):
            normalized.append(f"{key[0]}.{key[1]}")
        else:
            normalized.append(str(key))
    return sorted(set(normalized))


def _fallback_modules(user) -> list[dict]:
    defaults = [
        ("dashboard", "Dashboard", "dashboard", "#0F766E", "/dashboard", "", 1),
        ("pos", "POS", "point_of_sale", "#2563EB", "/pos", "billing.invoices", 2),
        ("billing", "Billing", "receipt_long", "#10B981", "/billing", "billing.invoices", 3),
        ("reports", "Reports", "bar_chart", "#EF4444", "/reports", "reports.account_summary", 4),
        ("products", "Products", "category", "#22D3EE", "/products", "commerce.inventory", 5),
        ("crm", "CRM", "groups", "#0EA5E9", "/crm", "", 6),
        ("devices", "Devices", "devices", "#64748B", "/devices", "", 7),
        ("sales", "Sales", "shopping_cart", "#F59E0B", "/sales", "commerce.orders", 8),
        ("selfcheckout", "Self Checkout", "qr_code_scanner", "#7C3AED", "/self-checkout", "billing.invoices", 9),
        ("settings", "Settings", "settings", "#94A3B8", "/settings", "settings.advanced", 10),
    ]
    enabled = _enabled_features(user)
    rows = []
    for key, title, icon, color, route, feature, order in defaults:
        allowed = not feature or enabled.get(feature, False) or user_can(user, key) or user_can(user, f"{key}_view")
        if key in {"dashboard", "settings"}:
            allowed = allowed or bool(getattr(user, "is_authenticated", False))
        if not allowed:
            continue
        rows.append(
            {
                "key": key,
                "name": title,
                "title": title,
                "icon": icon,
                "color": color,
                "route": route,
                "web_url": route,
                "api_namespace": "/fastapi/crud",
                "permission": key,
                "visible": True,
                "enabled": True,
                "order": order,
                "settings": {"auto_generated": True, "feature_key": feature},
            }
        )
    if not rows:
        rows.append(defaults[0] and {
            "key": "dashboard",
            "name": "Dashboard",
            "title": "Dashboard",
            "icon": "dashboard",
            "color": "#0F766E",
            "route": "/dashboard",
            "web_url": "/dashboard",
            "api_namespace": "/fastapi/crud",
            "permission": "dashboard",
            "visible": True,
            "enabled": True,
            "order": 1,
            "settings": {"auto_generated": True},
        })
    return rows


def _ensure_module_permissions(permission_rows: dict, module_rows: list[dict], *, user) -> None:
    for row in module_rows:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        permission_key = row.get("permission")
        if permission_key is True or str(permission_key).lower() in {"true", "1"}:
            row["permission"] = key
        elif not permission_key:
            row["permission"] = key
        effective_key = str(row["permission"])
        existing = permission_rows.get(effective_key) or permission_rows.get(key) or {}
        if existing and any(existing.values()):
            permission_rows[effective_key] = existing
            continue
        allowed = bool(getattr(user, "is_superuser", False) or getattr(user, "is_staff", False) or row.get("enabled", True))
        permission_rows[effective_key] = {
            "view": allowed,
            "create": allowed,
            "edit": allowed,
            "delete": allowed and key not in {"dashboard", "reports"},
            "export": allowed,
            "print": allowed,
            "approve": allowed and key in {"billing", "sales", "purchases"},
            "manage": allowed and key in {"settings", "devices"},
        }
