from __future__ import annotations

from django.http import JsonResponse

from .models import DynamicModule
from .services import audit, register_device, user_can


class EnterpriseDeviceTrackingMiddleware:
    """Tracks Flutter/POS/kiosk devices without changing existing web login flows."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/") and getattr(request, "user", None) and request.user.is_authenticated:
            device_id = request.headers.get("X-Device-Id")
            if device_id:
                register_device(
                    request,
                    device_id,
                    platform=request.headers.get("X-Platform") or "",
                    app_version=request.headers.get("X-App-Version") or "",
                )
        return self.get_response(request)


class EnterpriseAPIPermissionMiddleware:
    """Server-side platform/module gate for enterprise-control APIs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or user.is_staff or user.is_superuser:
            return self.get_response(request)
        is_enterprise_surface = request.path.startswith("/api/enterprise/") or request.headers.get("X-Enterprise-Control")
        if not is_enterprise_surface:
            return self.get_response(request)
        platform = request.headers.get("X-Platform") or request.GET.get("platform") or "api"
        if platform in {"app", "pos", "kiosk", "web", "api"} and not user_can(user, f"{platform}_access"):
            return JsonResponse({"detail": f"Missing platform permission: {platform}_access"}, status=403)
        module_key = _module_from_path(request.path)
        if module_key and DynamicModule.objects.filter(key=module_key, is_enabled=False).exists():
            return JsonResponse({"detail": f"Module disabled: {module_key}"}, status=403)
        return self.get_response(request)


class EnterpriseAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.path.startswith("/api/enterprise/"):
            try:
                audit(
                    getattr(request, "user", None),
                    f"api.{request.method.lower()}",
                    request=request,
                    target=request.path[:180],
                    platform=request.headers.get("X-Platform") or "",
                    metadata={"status": getattr(response, "status_code", None)},
                )
            except Exception:
                pass
        return response


def _module_from_path(path: str) -> str:
    parts = [p for p in (path or "").split("/") if p]
    if not parts:
        return ""
    aliases = {
        "products": "inventory",
        "orders": "orders",
        "crm": "crm",
        "analytics": "analytics",
        "reports": "reports",
        "payments": "billing",
        "pos": "pos",
    }
    for part in parts:
        if part in aliases:
            return aliases[part]
    return ""
