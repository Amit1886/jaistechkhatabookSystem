from django.contrib import admin

from .models import (
    Department,
    PermissionMaster,
    PermissionNode,
    Role,
    RolePermission,
    RoleTemplate,
    RoleTemplatePermission,
    UserPermissionGraph,
    UserPermissionOverride,
)


@admin.register(PermissionMaster)
class PermissionMasterAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "module", "is_active")
    list_filter = ("module", "is_active")
    search_fields = ("key", "label", "description")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "is_system", "is_active")
    list_filter = ("is_system", "is_active")
    search_fields = ("key", "label")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission")
    search_fields = ("role__key", "permission__key")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("key", "name")


@admin.register(PermissionNode)
class PermissionNodeAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "module", "department", "is_active")
    list_filter = ("module", "department", "is_active")
    search_fields = ("key", "label", "description")


class RoleTemplatePermissionInline(admin.TabularInline):
    model = RoleTemplatePermission
    extra = 0


@admin.register(RoleTemplate)
class RoleTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "department", "is_system", "is_active")
    list_filter = ("department", "is_system", "is_active")
    search_fields = ("key", "label")
    inlines = [RoleTemplatePermissionInline]


@admin.register(UserPermissionGraph)
class UserPermissionGraphAdmin(admin.ModelAdmin):
    list_display = ("user", "seller", "role", "inherit_from_owner", "is_active", "updated_at")
    list_filter = ("seller", "role", "inherit_from_owner", "is_active")
    search_fields = ("user__email", "user__username", "user__mobile")


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    list_display = ("user", "seller", "permission", "effect", "updated_at")
    list_filter = ("seller", "effect")
    search_fields = ("user__email", "user__username", "permission__key", "permission__label")
