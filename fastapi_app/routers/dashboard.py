from fastapi import APIRouter, Depends

from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/dashboard", tags=["dynamic-dashboard"])


@router.get("/")
def dashboard(platform: str = "app", user=Depends(current_access_user)):
    widgets = []
    try:
        from enterprise_control.models import DashboardWidget

        rows = DashboardWidget.objects.filter(is_enabled=True).select_related("workspace", "module").order_by("order", "title")
        widgets = [
            {
                "key": row.key,
                "title": row.title,
                "type": row.widget_type,
                "module": row.module.key if row.module else "",
                "permission": row.permission_key,
                "data_source": row.data_source,
                "config": row.config or {},
                "order": row.order,
            }
            for row in rows[:100]
        ]
    except Exception:
        widgets = []
    if not widgets:
        widgets = [
            {"key": "sales_today", "title": "Sales Today", "type": "metric", "value": 0, "config": {"accent": "#0F766E"}},
            {"key": "offline_queue", "title": "Offline Queue", "type": "status", "value": "Ready", "config": {"accent": "#2563EB"}},
            {"key": "dynamic_models", "title": "Dynamic Models", "type": "metric", "value": "Auto", "config": {"accent": "#F59E0B"}},
        ]
    return {"platform": platform, "widgets": widgets, "layout": {"columns": 4, "density": "comfortable"}}


@router.get("/kpis")
def kpis(user=Depends(current_access_user)):
    return {
        "results": [
            {"key": "users", "label": "Users", "value": _count_model("accounts", "User")},
            {"key": "products", "label": "Products", "value": _count_model("commerce", "Product")},
            {"key": "parties", "label": "Parties", "value": _count_model("khataapp", "Party")},
        ]
    }


def _count_model(app_label: str, model_name: str) -> int:
    try:
        from django.apps import apps

        model = apps.get_model(app_label, model_name)
        return model.objects.count()
    except Exception:
        return 0
