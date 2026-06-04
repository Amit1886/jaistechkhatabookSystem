from django.contrib import admin
from django.core.cache import cache

from core.models import EnterpriseSetting, OfflineSyncBatch, OfflineSyncConflict, OfflineSyncOperation


@admin.register(EnterpriseSetting)
class EnterpriseSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "scope", "data_type", "env_key", "is_active", "updated_at")
    list_filter = ("scope", "data_type", "is_active")
    search_fields = ("key", "label", "env_key", "help_text")
    readonly_fields = ("updated_at",)
    fieldsets = (
        ("Setting", {"fields": ("key", "label", "scope", "data_type", "help_text", "is_active")}),
        ("Values", {"fields": ("value", "encrypted_value", "env_key", "default_value")}),
        ("Audit", {"fields": ("updated_by", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user if request.user.is_authenticated else None
        super().save_model(request, obj, form, change)
        cache.delete("enterprise:public_settings:v1")


class OfflineSyncOperationInline(admin.TabularInline):
    model = OfflineSyncOperation
    extra = 0
    readonly_fields = ("client_id", "model_key", "operation", "object_pk", "status", "error", "processed_at")
    can_delete = False


@admin.register(OfflineSyncBatch)
class OfflineSyncBatchAdmin(admin.ModelAdmin):
    list_display = ("device_id", "user", "status", "operation_count", "success_count", "error_count", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("device_id", "user__email")
    readonly_fields = tuple(field.name for field in OfflineSyncBatch._meta.fields)
    inlines = [OfflineSyncOperationInline]

    def has_add_permission(self, request):
        return False


@admin.register(OfflineSyncOperation)
class OfflineSyncOperationAdmin(admin.ModelAdmin):
    list_display = ("client_id", "model_key", "operation", "object_pk", "status", "created_at", "processed_at")
    list_filter = ("status", "operation", "model_key")
    search_fields = ("client_id", "model_key", "object_pk", "error")
    readonly_fields = tuple(field.name for field in OfflineSyncOperation._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(OfflineSyncConflict)
class OfflineSyncConflictAdmin(admin.ModelAdmin):
    list_display = ("model_key", "object_pk", "policy", "resolved", "created_at", "resolved_at")
    list_filter = ("resolved", "policy", "model_key")
    search_fields = ("model_key", "object_pk")
    readonly_fields = tuple(field.name for field in OfflineSyncConflict._meta.fields)

    def has_add_permission(self, request):
        return False
