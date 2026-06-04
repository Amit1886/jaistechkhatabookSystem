from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("control/modules", views.DynamicModuleViewSet, basename="enterprise-module")
router.register("control/permissions", views.PermissionNodeViewSet, basename="enterprise-permission")
router.register("control/roles", views.RoleTemplateViewSet, basename="enterprise-role")
router.register("control/templates", views.PermissionTemplateViewSet, basename="enterprise-template")
router.register("control/workspaces", views.WorkspaceViewSet, basename="enterprise-workspace")
router.register("control/widgets", views.DashboardWidgetViewSet, basename="enterprise-widget")
router.register("control/themes", views.ThemeConfigViewSet, basename="enterprise-theme")
router.register("control/user-workspaces", views.UserWorkspaceViewSet, basename="enterprise-user-workspace")
router.register("control/user-permission-graphs", views.UserPermissionGraphViewSet, basename="enterprise-user-permission-graph")
router.register("control/user-permission-overrides", views.UserPermissionOverrideViewSet, basename="enterprise-user-permission-override")
router.register("control/device-sessions", views.DeviceSessionViewSet, basename="enterprise-device-session")
router.register("control/audit-logs", views.AuditLogViewSet, basename="enterprise-audit-log")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", views.dashboard_api, name="enterprise-dashboard-api"),
    path("permissions/", views.permissions_api, name="enterprise-permissions-api"),
    path("modules/", views.modules_api, name="enterprise-modules-api"),
    path("workspaces/", views.workspaces_api, name="enterprise-workspaces-api"),
    path("theme/", views.theme_api, name="enterprise-theme-api"),
    path("settings/", views.settings_api, name="enterprise-settings-api"),
    path("menu/", views.menu_api, name="enterprise-menu-api"),
    path("widgets/", views.widgets_api, name="enterprise-widgets-api"),
    path("reports/", views.reports_api, name="enterprise-reports-api"),
    path("analytics/", views.analytics_api, name="enterprise-analytics-api"),
    path("notifications/", views.notifications_api, name="enterprise-notifications-api"),
    path("devices/register/", views.device_register_api, name="enterprise-device-register-api"),
]
