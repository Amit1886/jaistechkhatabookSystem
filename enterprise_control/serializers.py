from __future__ import annotations

from rest_framework import serializers

from saas.models import PermissionNode, RoleTemplate, UserPermissionGraph, UserPermissionOverride

from .models import (
    AuditLog,
    DashboardWidget,
    DeviceSession,
    DynamicModule,
    PermissionTemplate,
    ThemeConfig,
    UserWorkspace,
    Workspace,
)


class DynamicModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicModule
        fields = "__all__"


class PermissionNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionNode
        fields = ("id", "key", "label", "description", "module", "parent", "is_active")


class RoleTemplateSerializer(serializers.ModelSerializer):
    permission_keys = serializers.SerializerMethodField()

    class Meta:
        model = RoleTemplate
        fields = ("id", "key", "label", "department", "is_system", "is_active", "permission_keys")

    def get_permission_keys(self, obj):
        return list(obj.role_edges.filter(effect="allow").values_list("permission__key", flat=True))


class PermissionTemplateSerializer(serializers.ModelSerializer):
    role_key = serializers.CharField(source="role.key", read_only=True)

    class Meta:
        model = PermissionTemplate
        fields = "__all__"


class WorkspaceSerializer(serializers.ModelSerializer):
    role_key = serializers.CharField(source="role.key", read_only=True)

    class Meta:
        model = Workspace
        fields = "__all__"


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = "__all__"


class ThemeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThemeConfig
        fields = "__all__"


class UserWorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWorkspace
        fields = "__all__"


class UserPermissionGraphSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPermissionGraph
        fields = "__all__"


class UserPermissionOverrideSerializer(serializers.ModelSerializer):
    permission_key = serializers.CharField(source="permission.key", read_only=True)

    class Meta:
        model = UserPermissionOverride
        fields = "__all__"


class DeviceSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSession
        fields = "__all__"
        read_only_fields = ("user", "ip_address", "user_agent", "last_seen_at")


class AuditLogSerializer(serializers.ModelSerializer):
    actor_label = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = ("actor", "ip_address", "created_at")

    def get_actor_label(self, obj):
        actor = obj.actor
        if not actor:
            return ""
        return getattr(actor, "email", "") or getattr(actor, "username", "") or str(actor.pk)
