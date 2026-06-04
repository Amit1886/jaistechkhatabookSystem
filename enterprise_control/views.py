from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import decorators, permissions, response, status, viewsets

from saas.models import PermissionNode, RoleTemplate, UserPermissionGraph, UserPermissionOverride

from .models import AuditLog, DashboardWidget, DeviceSession, DynamicModule, PermissionTemplate, ThemeConfig, UserWorkspace, Workspace
from .serializers import (
    AuditLogSerializer,
    DashboardWidgetSerializer,
    DeviceSessionSerializer,
    DynamicModuleSerializer,
    PermissionNodeSerializer,
    PermissionTemplateSerializer,
    RoleTemplateSerializer,
    ThemeConfigSerializer,
    UserPermissionGraphSerializer,
    UserPermissionOverrideSerializer,
    UserWorkspaceSerializer,
    WorkspaceSerializer,
)
from .services import apply_template_to_user, audit, bootstrap_payload, broadcast_enterprise_event, central_app_config, permission_matrix, register_device, theme_payload


class IsEnterpriseAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


class DynamicModuleViewSet(viewsets.ModelViewSet):
    queryset = DynamicModule.objects.all()
    serializer_class = DynamicModuleSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("key", "name", "description")
    ordering_fields = ("order", "name", "updated_at")

    def perform_create(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "module.create", request=self.request, target=instance.key)
        broadcast_enterprise_event("modules", {"type": "module.created", "key": instance.key})

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "module.update", request=self.request, target=instance.key)
        broadcast_enterprise_event("modules", {"type": "module.updated", "key": instance.key})


class PermissionNodeViewSet(viewsets.ModelViewSet):
    queryset = PermissionNode.objects.all()
    serializer_class = PermissionNodeSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("key", "label", "module")
    ordering_fields = ("module", "key", "label")

    def perform_create(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "permission.create", request=self.request, target=instance.key)
        broadcast_enterprise_event("permissions", {"type": "permission.created", "key": instance.key})

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "permission.update", request=self.request, target=instance.key)
        broadcast_enterprise_event("permissions", {"type": "permission.updated", "key": instance.key})


class RoleTemplateViewSet(viewsets.ModelViewSet):
    queryset = RoleTemplate.objects.all()
    serializer_class = RoleTemplateSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("key", "label")


class PermissionTemplateViewSet(viewsets.ModelViewSet):
    queryset = PermissionTemplate.objects.select_related("role").all()
    serializer_class = PermissionTemplateSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("key", "name")

    @decorators.action(detail=True, methods=["post"], url_path="apply")
    def apply(self, request, pk=None):
        template = self.get_object()
        user_id = request.data.get("user_id")
        user = get_object_or_404(get_user_model(), pk=user_id)
        graph = apply_template_to_user(user, template, actor=request.user)
        return response.Response({"ok": True, "graph_id": graph.pk, "template": template.key})


class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = Workspace.objects.select_related("role").all()
    serializer_class = WorkspaceSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("key", "name", "role__key")

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "workspace.update", request=self.request, target=instance.key)
        broadcast_enterprise_event("dashboard", {"type": "workspace.updated", "key": instance.key})


class DashboardWidgetViewSet(viewsets.ModelViewSet):
    queryset = DashboardWidget.objects.select_related("workspace", "module").all()
    serializer_class = DashboardWidgetSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("key", "title", "permission_key")

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "widget.update", request=self.request, target=instance.key)
        broadcast_enterprise_event("dashboard", {"type": "widget.updated", "key": instance.key})


class ThemeConfigViewSet(viewsets.ModelViewSet):
    queryset = ThemeConfig.objects.all()
    serializer_class = ThemeConfigSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("key", "name", "brand_name")

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "theme.update", request=self.request, target=instance.key)
        broadcast_enterprise_event("dashboard", {"type": "theme.updated", "key": instance.key})


class UserWorkspaceViewSet(viewsets.ModelViewSet):
    queryset = UserWorkspace.objects.select_related("user", "workspace", "role").all()
    serializer_class = UserWorkspaceSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("user__email", "user__username", "workspace__key", "role__key")


class UserPermissionGraphViewSet(viewsets.ModelViewSet):
    queryset = UserPermissionGraph.objects.select_related("user", "role", "seller").all()
    serializer_class = UserPermissionGraphSerializer
    permission_classes = [IsEnterpriseAdmin]


class UserPermissionOverrideViewSet(viewsets.ModelViewSet):
    queryset = UserPermissionOverride.objects.select_related("user", "permission", "seller").all()
    serializer_class = UserPermissionOverrideSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("user__email", "user__username", "permission__key", "permission__label")

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request.user, "permission_override.update", request=self.request, target=f"user:{instance.user_id}:{instance.permission.key}")
        broadcast_enterprise_event("permissions", {"type": "permission_override.updated", "user_id": instance.user_id})


class DeviceSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceSession.objects.select_related("user").all()
    serializer_class = DeviceSessionSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("user__email", "device_id", "platform")


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsEnterpriseAdmin]
    search_fields = ("action", "target", "actor__email")


@decorators.api_view(["GET"])
@decorators.permission_classes([permissions.AllowAny])
def system_app_config_api(request):
    platform = request.GET.get("platform") or request.GET.get("mode") or "app"
    return response.Response(central_app_config(request.user, platform=platform, request=request))


@decorators.api_view(["GET"])
def dashboard_api(request):
    platform = request.GET.get("platform") or request.GET.get("mode") or "web"
    from fastapi_app.routers import mobile as fastapi_mobile

    return response.Response(fastapi_mobile.bootstrap(platform=platform, user=request.user))


@decorators.api_view(["GET"])
def permissions_api(request):
    from fastapi_app.routers import mobile as fastapi_mobile

    return response.Response(fastapi_mobile.modules(platform=request.GET.get("platform") or "web", user=request.user).get("permissions", {}))


@decorators.api_view(["GET"])
def modules_api(request):
    from fastapi_app.routers import mobile as fastapi_mobile

    return response.Response(fastapi_mobile.modules(platform=request.GET.get("platform") or "web", user=request.user)["results"])


@decorators.api_view(["GET"])
def workspaces_api(request):
    payload = bootstrap_payload(request.user, request=request, platform=request.GET.get("platform") or "web")
    return response.Response(payload["workspace"])


@decorators.api_view(["GET"])
def theme_api(request):
    return response.Response(theme_payload(platform=request.GET.get("platform") or "web"))


@decorators.api_view(["GET"])
def menu_api(request):
    from fastapi_app.routers import mobile as fastapi_mobile

    return response.Response(fastapi_mobile.menu(platform=request.GET.get("platform") or "web", user=request.user)["results"])


@decorators.api_view(["GET"])
def widgets_api(request):
    payload = bootstrap_payload(request.user, request=request, platform=request.GET.get("platform") or "web")
    return response.Response(payload["widgets"])


@decorators.api_view(["GET"])
def settings_api(request):
    from fastapi_app.routers import mobile as fastapi_mobile

    payload = fastapi_mobile.bootstrap(platform=request.GET.get("platform") or "web", user=request.user)
    return response.Response({"workspace": payload["workspace"], "theme": payload["theme"], "realtime": payload["realtime"]})


@decorators.api_view(["GET"])
def reports_api(request):
    return response.Response({"reports": [], "entrypoints": {m.key: m.web_url for m in DynamicModule.objects.filter(is_enabled=True, key__in=["reports", "analytics"])}})


@decorators.api_view(["GET"])
def analytics_api(request):
    return response.Response({"status": "ready", "widgets": bootstrap_payload(request.user, platform="web")["widgets"]})


@decorators.api_view(["GET"])
def notifications_api(request):
    return response.Response({"items": [], "unread_count": 0})


@decorators.api_view(["POST"])
def device_register_api(request):
    device = register_device(
        request,
        request.data.get("device_id") or request.headers.get("X-Device-Id") or "",
        platform=request.data.get("platform") or request.headers.get("X-Platform") or "",
        app_version=request.data.get("app_version") or request.headers.get("X-App-Version") or "",
    )
    if not device:
        return response.Response({"detail": "device_id required"}, status=status.HTTP_400_BAD_REQUEST)
    audit(request.user, "device.register", request=request, target=device.device_id, platform=device.platform)
    return response.Response(DeviceSessionSerializer(device).data)
