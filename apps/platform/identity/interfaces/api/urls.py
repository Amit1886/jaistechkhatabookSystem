from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.platform.identity.interfaces.api.views import (
    ActivitySessionViewSet,
    AuditLogViewSet,
    BranchViewSet,
    CompanyViewSet,
    DynamicFieldViewSet,
    DynamicModuleViewSet,
    EnterprisePermissionViewSet,
    EnterpriseRoleViewSet,
    FieldPermissionViewSet,
    LoginHistoryViewSet,
    PermissionOverrideViewSet,
    RolePermissionViewSet,
    SmartNotificationViewSet,
    TenantMembershipViewSet,
    TenantViewSet,
    UserDeviceViewSet,
    VersionHistoryViewSet,
)

router = DefaultRouter()
router.register("tenants", TenantViewSet)
router.register("companies", CompanyViewSet)
router.register("branches", BranchViewSet)
router.register("memberships", TenantMembershipViewSet)
router.register("roles", EnterpriseRoleViewSet)
router.register("permissions", EnterprisePermissionViewSet)
router.register("role-permissions", RolePermissionViewSet)
router.register("dynamic-modules", DynamicModuleViewSet)
router.register("dynamic-fields", DynamicFieldViewSet)
router.register("field-permissions", FieldPermissionViewSet)
router.register("permission-overrides", PermissionOverrideViewSet)
router.register("activity-sessions", ActivitySessionViewSet)
router.register("audit-logs", AuditLogViewSet)
router.register("version-history", VersionHistoryViewSet)
router.register("notifications", SmartNotificationViewSet)
router.register("user-devices", UserDeviceViewSet)
router.register("login-history", LoginHistoryViewSet)

urlpatterns = [path("", include(router.urls))]
