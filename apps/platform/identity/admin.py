from django.contrib import admin

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


class TenantScopedAdmin(admin.ModelAdmin):
    list_filter = ("tenant",) if hasattr(Tenant, "_meta") else ()


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "owner", "created_at")
    search_fields = ("name", "slug", "owner__email")
    list_filter = ("status", "created_at")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "gst_number", "is_active", "created_at")
    search_fields = ("name", "legal_name", "gst_number", "tenant__name")
    list_filter = ("is_active", "tenant")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "company", "tenant", "is_active")
    search_fields = ("name", "code", "company__name", "tenant__name")
    list_filter = ("is_active", "tenant", "company")


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "company", "branch", "is_owner", "is_active")
    search_fields = ("user__email", "user__username", "tenant__name")
    list_filter = ("tenant", "is_owner", "is_active")


@admin.register(EnterpriseRole)
class EnterpriseRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "tenant", "parent", "is_system", "is_active")
    search_fields = ("name", "key", "tenant__name")
    list_filter = ("tenant", "is_system", "is_active")


@admin.register(EnterprisePermission)
class EnterprisePermissionAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "scope", "module", "tenant", "is_active")
    search_fields = ("key", "label", "module__key", "tenant__name")
    list_filter = ("scope", "tenant", "is_active")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "allowed", "updated_at")
    search_fields = ("role__name", "permission__key")
    list_filter = ("allowed", "role__tenant")


@admin.register(DynamicModule)
class DynamicModuleAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "app_label", "menu_key", "tenant", "is_active")
    search_fields = ("key", "label", "app_label", "menu_key")
    list_filter = ("tenant", "is_active")


@admin.register(DynamicField)
class DynamicFieldAdmin(admin.ModelAdmin):
    list_display = ("module", "key", "label", "field_name", "is_sensitive", "is_active")
    search_fields = ("module__key", "key", "label", "model_path", "field_name")
    list_filter = ("module", "is_sensitive", "is_active")


@admin.register(FieldPermission)
class FieldPermissionAdmin(admin.ModelAdmin):
    list_display = ("field", "tenant", "role", "user", "access")
    search_fields = ("field__key", "role__name", "user__email")
    list_filter = ("access", "tenant")


@admin.register(PermissionOverride)
class PermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "permission", "tenant", "allowed", "starts_at", "expires_at")
    search_fields = ("user__email", "permission__key", "reason")
    list_filter = ("allowed", "tenant")


@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "ip_address", "is_active", "last_seen_at", "started_at")
    search_fields = ("user__email", "session_key", "ip_address")
    list_filter = ("is_active", "tenant", "last_seen_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "user", "tenant", "object_type", "object_id", "actor_ip")
    search_fields = ("action", "user__email", "object_type", "object_id", "actor_ip")
    list_filter = ("action", "tenant", "created_at")
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(VersionHistory)
class VersionHistoryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "object_type", "object_id", "version", "user", "tenant")
    search_fields = ("object_type", "object_id", "user__email")
    list_filter = ("tenant", "created_at")
    readonly_fields = tuple(field.name for field in VersionHistory._meta.fields)


@admin.register(SmartNotification)
class SmartNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "tenant", "severity", "status", "created_at")
    search_fields = ("title", "message", "user__email")
    list_filter = ("severity", "status", "tenant")


@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "name", "status", "ip_address", "last_seen_at")
    search_fields = ("user__email", "fingerprint", "name", "ip_address")
    list_filter = ("status", "tenant", "last_seen_at")


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "email", "user", "tenant", "result", "ip_address", "reason")
    search_fields = ("email", "user__email", "ip_address", "reason")
    list_filter = ("result", "tenant", "created_at")
    readonly_fields = tuple(field.name for field in LoginHistory._meta.fields)
