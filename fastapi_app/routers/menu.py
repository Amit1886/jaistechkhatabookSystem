from fastapi import APIRouter, Depends

from core.metadata.scanner import scan_models
from enterprise_control.services import button_payload, launcher_payload, sidebar_tree, visible_modules_for_user
from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/menu", tags=["dynamic-menu"])


def _module_rows_from_enterprise_control(platform: str):
    try:
        from enterprise_control.models import DynamicModule

        rows = DynamicModule.objects.filter(is_enabled=True).order_by("order", "name")
        if platform:
            rows = rows.filter(access_platforms__contains=[platform])
        return [
            {
                "key": row.key,
                "label": row.name,
                "icon": row.icon or "apps",
                "color": row.color or "#2563EB",
                "route": row.app_route or row.web_url or f"/{row.key}",
                "web_url": row.web_url,
                "api_namespace": row.api_namespace,
                "order": row.order,
                "permissions": row.required_permissions or [],
                "settings": row.settings or {},
            }
            for row in rows
        ]
    except Exception:
        return []


@router.get("/")
def menu(platform: str = "app", user=Depends(current_access_user)):
    rows = _module_rows_from_enterprise_control(platform)
    if not rows:
        app_labels = sorted({meta["app_label"] for meta in scan_models()})
        rows = [
            {
                "key": label,
                "label": label.replace("_", " ").title(),
                "icon": "apps",
                "color": "#2563EB",
                "route": f"/dynamic/{label}",
                "web_url": f"/{label}/",
                "api_namespace": f"/fastapi/crud",
                "order": index + 100,
                "permissions": [],
                "settings": {"auto_generated": True},
            }
            for index, label in enumerate(app_labels[:80])
        ]
    return {
        "platform": platform,
        "count": len(rows),
        "results": rows,
        "launcher": launcher_payload(user, modules=visible_modules_for_user(user, platform=platform), platform=platform),
        "sidebar": sidebar_tree(user, modules=visible_modules_for_user(user, platform=platform), platform=platform),
        "buttons": button_payload(user, platform=platform),
    }


@router.get("/launcher")
def launcher(platform: str = "app", user=Depends(current_access_user)):
    return {"platform": platform, "results": launcher_payload(user, platform=platform)}


@router.get("/sidebar")
def sidebar(platform: str = "app", user=Depends(current_access_user)):
    return {"platform": platform, "results": sidebar_tree(user, platform=platform)}


@router.get("/buttons")
def buttons(platform: str = "app", user=Depends(current_access_user)):
    return {"platform": platform, "results": button_payload(user, platform=platform)}


@router.get("/workspaces")
def workspaces(user=Depends(current_access_user)):
    try:
        from enterprise_control.models import Workspace

        rows = Workspace.objects.filter(is_active=True).order_by("order", "name")
        return {
            "count": rows.count(),
            "results": [
                {
                    "key": row.key,
                    "name": row.name,
                    "platform": row.platform,
                    "landing_route": row.landing_route,
                    "module_keys": row.module_keys,
                    "menu_schema": row.menu_schema,
                    "layout_schema": row.layout_schema,
                    "is_default": row.is_default,
                }
                for row in rows
            ],
        }
    except Exception:
        return {"count": 0, "results": []}
