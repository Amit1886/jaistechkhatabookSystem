from fastapi import APIRouter, Depends

from django.apps import apps

from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/plugins", tags=["plugin-system"])


@router.get("/")
def plugins(user=Depends(current_access_user)):
    plugin_apps = []
    for config in apps.get_app_configs():
        if config.label.startswith("addon") or config.name.startswith("addons.") or "plugin" in config.label:
            plugin_apps.append(
                {
                    "label": config.label,
                    "name": config.name,
                    "verbose_name": config.verbose_name,
                    "models": [model._meta.label_lower for model in config.get_models()],
                }
            )
    return {
        "count": len(plugin_apps),
        "results": plugin_apps,
        "extension_points": [
            "metadata.scanner",
            "dynamic_api.router",
            "mobile.screen_renderer",
            "offline.sync_handler",
            "dashboard.widget_provider",
            "report.export_provider",
        ],
    }


@router.get("/manifest")
def manifest(user=Depends(current_access_user)):
    return {
        "version": "1.0.0",
        "contract": {
            "backend": "Django app with models/admin plus optional FastAPI router",
            "mobile": "metadata widgets rendered by Flutter dynamic renderer",
            "permissions": "Django permissions or enterprise permission keys",
            "settings": "public settings plus encrypted private settings",
        },
    }
