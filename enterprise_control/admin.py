from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    APITestLog,
    APIRegistry,
    AppFeatureMapping,
    AuditLog,
    DashboardWidget,
    DeviceSession,
    DynamicButton,
    DynamicMenuItem,
    DynamicModule,
    EnterpriseSetting,
    PermissionTemplate,
    ThemeConfig,
    UserWorkspace,
    Workspace,
)
from .services import refresh_feature_mapping_status, sync_fastapi_routes, test_registered_api


admin.site.site_header = "Billentra Enterprise Superadmin"
admin.site.site_title = "Billentra Control Center"
admin.site.index_title = "Enterprise App, API & Settings Control"


class MobileAppConnectionForm(forms.Form):
    public_ip = forms.CharField(
        label="Public IP / Domain",
        initial="49.43.113.95",
        help_text="Example: 49.43.113.95 or api.yourdomain.com",
    )
    port = forms.IntegerField(label="Port", initial=57824, min_value=1, max_value=65535)
    scheme = forms.ChoiceField(label="Protocol", choices=(("http", "HTTP"), ("https", "HTTPS")), initial="http")
    android_emulator_host = forms.CharField(
        label="Android Emulator Host",
        initial="10.0.2.2",
        help_text="Android Studio emulator uses 10.0.2.2 to reach this PC.",
    )
    save_emulator_url = forms.BooleanField(
        label="Also save emulator URL",
        required=False,
        initial=True,
    )

    def clean_public_ip(self):
        value = self.cleaned_data["public_ip"].strip().rstrip("/")
        return value.replace("http://", "").replace("https://", "").split("/")[0]

    def clean_android_emulator_host(self):
        value = self.cleaned_data["android_emulator_host"].strip().rstrip("/")
        return value.replace("http://", "").replace("https://", "").split("/")[0]


@admin.register(DynamicModule)
class DynamicModuleAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "order", "is_enabled", "is_core", "updated_at")
    list_filter = ("is_enabled", "is_core")
    search_fields = ("key", "name", "description")
    list_editable = ("order", "is_enabled")


@admin.register(EnterpriseSetting)
class EnterpriseSettingAdmin(admin.ModelAdmin):
    change_list_template = "admin/enterprise_control/enterprisesetting/change_list.html"
    list_display = ("category", "key", "label", "current_value", "data_type", "is_public", "is_secret", "is_active", "updated_at", "mobile_setup_link")
    list_filter = ("category", "data_type", "is_public", "is_secret", "is_active")
    search_fields = ("key", "label", "description")
    list_editable = ("is_public", "is_active")
    fieldsets = (
        ("Setting", {"fields": ("category", "key", "label", "description", "data_type")}),
        ("Value", {"fields": ("value", "default_value")}),
        ("Access", {"fields": ("platform_access", "is_public", "is_secret", "is_active")}),
    )

    def get_urls(self):
        return [
            path(
                "mobile-app-connection/",
                self.admin_site.admin_view(self.mobile_app_connection_view),
                name="enterprise_control_mobile_app_connection",
            ),
            *super().get_urls(),
        ]

    def mobile_app_connection_view(self, request):
        if request.method == "POST":
            form = MobileAppConnectionForm(request.POST)
            if form.is_valid():
                scheme = form.cleaned_data["scheme"]
                public_ip = form.cleaned_data["public_ip"]
                port = form.cleaned_data["port"]
                emulator_host = form.cleaned_data["android_emulator_host"]
                public_url = f"{scheme}://{public_ip}:{port}"
                emulator_url = f"{scheme}://{emulator_host}:{port}"

                self._save_url_setting(
                    "api_base_url",
                    "Mobile App Live API URL",
                    public_url,
                    request.user,
                    description="Android app real-device/public backend URL. The app reads this automatically after login/bootstrap.",
                )
                self._save_url_setting(
                    "backend_url",
                    "Backend Live URL",
                    public_url,
                    request.user,
                    description="Main backend URL shared with mobile, dashboard, and API clients.",
                )
                if form.cleaned_data["save_emulator_url"]:
                    self._save_url_setting(
                        "android_emulator_api_base_url",
                        "Android Emulator API URL",
                        emulator_url,
                        request.user,
                        description="Use this only inside Android Studio emulator.",
                    )

                messages.success(
                    request,
                    f"Mobile app live API URL saved: {public_url}. Android emulator URL: {emulator_url}",
                )
                return redirect(reverse("admin:enterprise_control_mobile_app_connection"))
        else:
            initial = self._initial_mobile_connection(request)
            form = MobileAppConnectionForm(initial=initial)

        context = {
            **self.admin_site.each_context(request),
            "title": "Mobile App Live URL Setup",
            "form": form,
            "saved_urls": self._saved_mobile_urls(),
        }
        return render(request, "admin/enterprise_control/mobile_app_connection.html", context)

    def _initial_mobile_connection(self, request):
        setting = EnterpriseSetting.objects.filter(key="api_base_url", is_active=True).first()
        raw = ""
        if setting:
            value = setting.value
            raw = value.get("url") or value.get("value") if isinstance(value, dict) else str(value or "")
        if not raw:
            raw = f"http://49.43.113.95:57824"
        cleaned = raw.replace("http://", "").replace("https://", "")
        host_port = cleaned.split("/", 1)[0]
        host, _, port = host_port.partition(":")
        return {
            "scheme": "https" if raw.startswith("https://") else "http",
            "public_ip": host or "49.43.113.95",
            "port": int(port or 57824),
            "android_emulator_host": "10.0.2.2",
            "save_emulator_url": True,
        }

    def _save_url_setting(self, key, label, url, user, *, description):
        EnterpriseSetting.objects.update_or_create(
            key=key,
            defaults={
                "category": "mobile",
                "label": label,
                "description": description,
                "data_type": "url",
                "value": {"url": url, "value": url},
                "default_value": {"url": url, "value": url},
                "platform_access": ["app", "mobile", "desktop", "api"],
                "is_secret": False,
                "is_public": True,
                "is_active": True,
                "updated_by": user,
            },
        )

    def _saved_mobile_urls(self):
        rows = EnterpriseSetting.objects.filter(
            key__in=["api_base_url", "backend_url", "android_emulator_api_base_url"],
            is_active=True,
        ).order_by("key")
        urls = []
        for row in rows:
            value = row.value
            url = value.get("url") or value.get("value") if isinstance(value, dict) else str(value or "")
            urls.append({"label": row.label, "key": row.key, "url": url})
        return urls

    @admin.display(description="Mobile Setup")
    def mobile_setup_link(self, obj):
        url = reverse("admin:enterprise_control_mobile_app_connection")
        return format_html('<a class="button" href="{}">Open Mobile Setup</a>', url)

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Current Value")
    def current_value(self, obj):
        value = obj.value
        if obj.is_secret:
            return "***"
        if isinstance(value, dict):
            return value.get("value") or value.get("url") or value.get("text") or value
        return value


@admin.register(APIRegistry)
class APIRegistryAdmin(admin.ModelAdmin):
    list_display = ("method", "endpoint", "module", "status", "connected_apps_label", "last_response_status", "last_response_time_ms", "last_usage_at", "is_active")
    list_filter = ("method", "module", "status", "source", "auth_required", "is_active")
    search_fields = ("name", "endpoint", "module", "permission_keys", "connected_apps")
    list_editable = ("status", "is_active")
    readonly_fields = ("last_usage_at", "last_response_status", "last_response_time_ms", "last_error", "created_at", "updated_at")
    actions = ("sync_fastapi_routes_action", "test_selected_apis")
    fieldsets = (
        ("API", {"fields": ("name", "endpoint", "method", "module", "version", "source")}),
        ("Connection", {"fields": ("status", "connected_apps", "permission_keys", "auth_required", "is_active")}),
        ("Live Status", {"fields": ("last_usage_at", "last_response_status", "last_response_time_ms", "last_error")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Connected Apps")
    def connected_apps_label(self, obj):
        return ", ".join(obj.connected_apps or [])

    @admin.action(description="Sync all FastAPI routes into API Registry")
    def sync_fastapi_routes_action(self, request, queryset):
        result = sync_fastapi_routes(actor=request.user)
        self.message_user(request, f"FastAPI sync complete: {result['total']} routes, {result['created']} created, {result['updated']} updated.")

    @admin.action(description="Test selected APIs now")
    def test_selected_apis(self, request, queryset):
        tested = 0
        failed = 0
        for api in queryset:
            log = test_registered_api(api, actor=request.user)
            tested += 1
            if log.error or not (200 <= log.status_code < 500):
                failed += 1
        self.message_user(request, f"API test complete: {tested} tested, {failed} failed.")


@admin.register(APITestLog)
class APITestLogAdmin(admin.ModelAdmin):
    list_display = ("api", "status_code", "response_time_ms", "auth_status", "actor", "created_at")
    list_filter = ("status_code", "auth_status", "created_at")
    search_fields = ("api__endpoint", "api__name", "error", "response_text")
    readonly_fields = ("api", "actor", "request_payload", "request_headers", "response_payload", "response_text", "status_code", "response_time_ms", "auth_status", "error", "created_at")


@admin.register(AppFeatureMapping)
class AppFeatureMappingAdmin(admin.ModelAdmin):
    list_display = ("feature_key", "feature_name", "module", "status", "platforms_label", "is_enabled", "last_checked_at")
    list_filter = ("status", "module", "is_enabled")
    search_fields = ("feature_key", "feature_name", "description", "required_apis")
    filter_horizontal = ("connected_apis",)
    list_editable = ("status", "is_enabled")
    actions = ("refresh_status_action",)
    fieldsets = (
        ("Feature", {"fields": ("feature_key", "feature_name", "module", "description", "is_enabled")}),
        ("API Mapping", {"fields": ("required_apis", "connected_apis", "status", "platforms")}),
        ("Monitoring", {"fields": ("last_checked_at",)}),
    )
    readonly_fields = ("last_checked_at",)

    @admin.display(description="Platforms")
    def platforms_label(self, obj):
        return ", ".join(obj.platforms or [])

    @admin.action(description="Refresh selected feature API status")
    def refresh_status_action(self, request, queryset):
        result = refresh_feature_mapping_status(actor=request.user)
        self.message_user(request, f"Feature mapping status refreshed: {result['updated']} rows updated.")


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0


class DynamicButtonInline(admin.TabularInline):
    model = DynamicButton
    extra = 0
    fields = ("key", "label", "action_type", "route", "icon", "color", "shape", "permission_key", "order", "is_enabled")


class DynamicMenuItemInline(admin.TabularInline):
    model = DynamicMenuItem
    extra = 0
    fk_name = "workspace"
    fields = ("key", "title", "parent", "module", "icon", "route", "badge", "order", "is_group", "is_enabled")


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "role", "platform", "is_default", "is_active", "order")
    list_filter = ("platform", "is_default", "is_active", "role")
    search_fields = ("key", "name", "role__key")
    list_editable = ("is_default", "is_active", "order")
    inlines = [DashboardWidgetInline, DynamicButtonInline, DynamicMenuItemInline]


@admin.register(PermissionTemplate)
class PermissionTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "role", "is_system", "is_active")
    list_filter = ("is_system", "is_active")
    search_fields = ("key", "name", "permission_keys")


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "widget_type", "workspace", "module", "permission_key", "order", "is_enabled")
    list_filter = ("widget_type", "workspace", "module", "is_enabled")
    search_fields = ("key", "title", "permission_key")
    list_editable = ("order", "is_enabled")


@admin.register(DynamicButton)
class DynamicButtonAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "module", "workspace", "action_type", "shape", "order", "is_primary", "is_enabled")
    list_filter = ("action_type", "shape", "module", "workspace", "is_primary", "is_enabled")
    search_fields = ("key", "label", "route", "api_endpoint", "service_key", "permission_key", "plan_keys", "role_keys")
    list_editable = ("order", "is_primary", "is_enabled")
    fieldsets = (
        ("Identity", {"fields": ("key", "label", "description", "module", "workspace")}),
        ("Action", {"fields": ("action_type", "route", "api_endpoint", "service_key")}),
        ("Design", {"fields": ("icon", "color", "gradient", "shape", "animation", "config")}),
        ("Access", {"fields": ("permission_key", "plan_keys", "role_keys", "platform_access")}),
        ("Publishing", {"fields": ("order", "is_primary", "is_enabled")}),
    )


@admin.register(DynamicMenuItem)
class DynamicMenuItemAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "parent", "module", "workspace", "badge", "order", "is_group", "is_enabled")
    list_filter = ("is_group", "is_enabled", "workspace", "module")
    search_fields = ("key", "title", "route", "badge", "permission_key")
    list_editable = ("order", "is_group", "is_enabled")
    fieldsets = (
        ("Menu Node", {"fields": ("key", "title", "parent", "workspace", "module")}),
        ("Navigation", {"fields": ("icon", "route", "badge", "color", "config")}),
        ("Access", {"fields": ("permission_key", "platform_access")}),
        ("Publishing", {"fields": ("order", "is_group", "is_enabled")}),
    )


@admin.register(ThemeConfig)
class ThemeConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "brand_name", "primary", "secondary", "is_default", "is_active", "updated_at")
    list_filter = ("is_default", "is_active")
    search_fields = ("key", "name", "brand_name")


@admin.register(UserWorkspace)
class UserWorkspaceAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "updated_at")
    list_filter = ("workspace", "role")
    search_fields = ("user__email", "user__username", "workspace__key", "role__key")


@admin.register(DeviceSession)
class DeviceSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "device_id", "platform", "app_version", "is_active", "last_seen_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__email", "device_id", "user_agent")
    readonly_fields = ("last_seen_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "target", "actor", "platform", "created_at")
    list_filter = ("action", "platform", "created_at")
    search_fields = ("action", "target", "actor__email", "actor__username")
    readonly_fields = ("actor", "action", "target", "platform", "ip_address", "metadata", "created_at")
