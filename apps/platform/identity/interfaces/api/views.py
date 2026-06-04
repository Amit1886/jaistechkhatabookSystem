from django.db.models import Count
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.platform.identity.interfaces.api.serializers import (
    ActivitySessionSerializer,
    AuditLogSerializer,
    BranchSerializer,
    CompanySerializer,
    DynamicFieldSerializer,
    DynamicModuleSerializer,
    EnterprisePermissionSerializer,
    EnterpriseRoleSerializer,
    FieldPermissionSerializer,
    LoginHistorySerializer,
    PermissionOverrideSerializer,
    RolePermissionSerializer,
    SmartNotificationSerializer,
    TenantMembershipSerializer,
    TenantSerializer,
    UserDeviceSerializer,
    VersionHistorySerializer,
)
from apps.platform.identity.models import (
    ActivitySession,
    AuditLog,
    Branch,
    Company,
    DynamicField,
    DynamicModule,
    EnterprisePermission,
    EnterpriseRole,
    FieldPermission,
    LoginHistory,
    PermissionOverride,
    RolePermission,
    SmartNotification,
    Tenant,
    TenantMembership,
    UserDevice,
    VersionHistory,
)


class EnterpriseAdminPermission(permissions.IsAdminUser):
    pass


class TenantScopedViewSet(viewsets.ModelViewSet):
    permission_classes = [EnterpriseAdminPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id and hasattr(qs.model, "tenant"):
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class TenantViewSet(TenantScopedViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer


class CompanyViewSet(TenantScopedViewSet):
    queryset = Company.objects.select_related("tenant").all()
    serializer_class = CompanySerializer


class BranchViewSet(TenantScopedViewSet):
    queryset = Branch.objects.select_related("tenant", "company").all()
    serializer_class = BranchSerializer


class TenantMembershipViewSet(TenantScopedViewSet):
    queryset = TenantMembership.objects.select_related("tenant", "company", "branch", "user").all()
    serializer_class = TenantMembershipSerializer


class EnterpriseRoleViewSet(TenantScopedViewSet):
    queryset = EnterpriseRole.objects.select_related("tenant", "parent").all()
    serializer_class = EnterpriseRoleSerializer


class EnterprisePermissionViewSet(TenantScopedViewSet):
    queryset = EnterprisePermission.objects.select_related("tenant", "module").all()
    serializer_class = EnterprisePermissionSerializer


class RolePermissionViewSet(TenantScopedViewSet):
    queryset = RolePermission.objects.select_related("role", "permission").all()
    serializer_class = RolePermissionSerializer


class DynamicModuleViewSet(TenantScopedViewSet):
    queryset = DynamicModule.objects.select_related("tenant").all()
    serializer_class = DynamicModuleSerializer


class DynamicFieldViewSet(TenantScopedViewSet):
    queryset = DynamicField.objects.select_related("module").all()
    serializer_class = DynamicFieldSerializer


class FieldPermissionViewSet(TenantScopedViewSet):
    queryset = FieldPermission.objects.select_related("tenant", "role", "user", "field").all()
    serializer_class = FieldPermissionSerializer


class PermissionOverrideViewSet(TenantScopedViewSet):
    queryset = PermissionOverride.objects.select_related("tenant", "user", "permission").all()
    serializer_class = PermissionOverrideSerializer


class ActivitySessionViewSet(TenantScopedViewSet):
    queryset = ActivitySession.objects.select_related("tenant", "user", "device").all()
    serializer_class = ActivitySessionSerializer
    http_method_names = ["get", "head", "options"]

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        since = timezone.now() - timezone.timedelta(minutes=10)
        qs = self.get_queryset()
        return Response(
            {
                "active_sessions": qs.filter(is_active=True, last_seen_at__gte=since).count(),
                "users_online": qs.filter(is_active=True, last_seen_at__gte=since).values("user").distinct().count(),
                "by_tenant": list(qs.values("tenant__name").annotate(total=Count("id")).order_by("-total")[:20]),
            }
        )


class AuditLogViewSet(TenantScopedViewSet):
    queryset = AuditLog.objects.select_related("tenant", "user").all()
    serializer_class = AuditLogSerializer
    http_method_names = ["get", "head", "options"]


class VersionHistoryViewSet(TenantScopedViewSet):
    queryset = VersionHistory.objects.select_related("tenant", "user").all()
    serializer_class = VersionHistorySerializer
    http_method_names = ["get", "head", "options"]


class SmartNotificationViewSet(TenantScopedViewSet):
    queryset = SmartNotification.objects.select_related("tenant", "user").all()
    serializer_class = SmartNotificationSerializer

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        obj = self.get_object()
        obj.status = SmartNotification.Status.READ
        obj.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(obj).data)


class UserDeviceViewSet(TenantScopedViewSet):
    queryset = UserDevice.objects.select_related("tenant", "user").all()
    serializer_class = UserDeviceSerializer


class LoginHistoryViewSet(TenantScopedViewSet):
    queryset = LoginHistory.objects.select_related("tenant", "user", "device").all()
    serializer_class = LoginHistorySerializer
    http_method_names = ["get", "head", "options"]
