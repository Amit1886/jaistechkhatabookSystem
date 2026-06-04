from django.contrib import admin

from distribution import models
from distribution.services.sync import publish_distribution_sync


@admin.register(models.Industry)
class IndustryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(models.AppPlatform)
class AppPlatformAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "platform_type", "icon", "sort_order", "is_active")
    list_filter = ("platform_type", "is_active")
    search_fields = ("name", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(models.FeatureRegistry)
class FeatureRegistryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "version", "rollout_status", "is_enabled", "updated_at")
    list_filter = ("rollout_status", "is_enabled", "supported_platforms", "industries")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("supported_platforms", "industries")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        publish_distribution_sync("feature.saved", {"slug": obj.slug, "version": obj.version, "enabled": obj.is_enabled})


@admin.register(models.ModuleRegistry)
class ModuleRegistryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "module_type", "version", "is_enabled", "sort_order", "updated_at")
    list_filter = ("module_type", "is_enabled", "supported_platforms", "industries")
    search_fields = ("name", "slug", "route_path", "component_key")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("supported_platforms", "features", "industries")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        publish_distribution_sync("module.saved", {"slug": obj.slug, "version": obj.version, "enabled": obj.is_enabled})


@admin.register(models.IndustryModuleMap)
class IndustryModuleMapAdmin(admin.ModelAdmin):
    list_display = ("industry", "module", "is_required", "default_enabled")
    list_filter = ("industry", "is_required", "default_enabled")


@admin.register(models.SoftwareBuild)
class SoftwareBuildAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "build_type", "platform", "version", "is_published", "allow_public_download", "published_at")
    list_filter = ("build_type", "platform", "is_published", "allow_public_download", "industries")
    search_fields = ("title", "slug", "version", "release_notes")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("industries", "modules")
    readonly_fields = ("sha256", "published_at", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        publish_distribution_sync("build.saved", {"slug": obj.slug, "version": obj.version, "published": obj.is_published})


@admin.register(models.DownloadPermission)
class DownloadPermissionAdmin(admin.ModelAdmin):
    list_display = ("build", "user", "industry", "can_view", "can_download", "can_launch", "can_install_beta", "expires_at")
    list_filter = ("can_view", "can_download", "can_launch", "can_install_beta", "industry")
    search_fields = ("build__title", "user__email")


@admin.register(models.AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = ("platform", "version", "min_supported_version", "force_update", "is_current", "updated_at")
    list_filter = ("platform", "force_update", "is_current")


@admin.register(models.RemoteConfig)
class RemoteConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "scope", "industry", "user", "device_uid", "version", "is_active", "updated_at")
    list_filter = ("scope", "is_active", "industry")
    search_fields = ("key", "device_uid", "user__email")

    def save_model(self, request, obj, form, change):
        if change:
            obj.version = (obj.version or 0) + 1
        super().save_model(request, obj, form, change)
        publish_distribution_sync("remote_config.saved", {"key": obj.key, "scope": obj.scope, "version": obj.version})


@admin.register(models.DeviceRegistry)
class DeviceRegistryAdmin(admin.ModelAdmin):
    list_display = ("device_uid", "device_type", "owner", "industry", "platform", "app_version", "authorized", "last_seen_at")
    list_filter = ("device_type", "authorized", "industry", "platform")
    search_fields = ("device_uid", "owner__email", "app_version")


@admin.register(models.AppInstallation)
class AppInstallationAdmin(admin.ModelAdmin):
    list_display = ("device", "build", "installed_version", "status", "last_sync_at", "updated_at")
    list_filter = ("status", "build")
    search_fields = ("device__device_uid", "build__title")


@admin.register(models.DownloadToken)
class DownloadTokenAdmin(admin.ModelAdmin):
    list_display = ("build", "user", "token", "expires_at", "used_at", "ip_address")
    list_filter = ("expires_at", "used_at")
    search_fields = ("token", "build__title", "user__email")

