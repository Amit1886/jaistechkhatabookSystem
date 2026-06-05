from rest_framework import serializers

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


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = "__all__"


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = "__all__"


class TenantMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantMembership
        fields = "__all__"


class EnterpriseRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnterpriseRole
        fields = "__all__"


class EnterprisePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnterprisePermission
        fields = "__all__"


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = "__all__"


class DynamicModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicModule
        fields = "__all__"


class DynamicFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicField
        fields = "__all__"


class FieldPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldPermission
        fields = "__all__"


class PermissionOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionOverride
        fields = "__all__"


class ActivitySessionSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = ActivitySession
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")


class AuditLogSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = tuple(field.name for field in model._meta.fields)


class VersionHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VersionHistory
        fields = "__all__"
        read_only_fields = tuple(field.name for field in model._meta.fields)


class SmartNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartNotification
        fields = "__all__"


class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = "__all__"


class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = "__all__"
        read_only_fields = tuple(field.name for field in model._meta.fields)
