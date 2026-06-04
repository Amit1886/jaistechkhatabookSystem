from __future__ import annotations

from django.conf import settings
from django.db import models


class DynamicModule(models.Model):
    """No-code module registry that controls web, Flutter, POS, kiosk, and API surfaces."""

    ACCESS_WEB = "web"
    ACCESS_APP = "app"
    ACCESS_POS = "pos"
    ACCESS_KIOSK = "kiosk"
    ACCESS_API = "api"
    ACCESS_CHOICES = (
        (ACCESS_WEB, "Web"),
        (ACCESS_APP, "Flutter App"),
        (ACCESS_POS, "POS"),
        (ACCESS_KIOSK, "Kiosk"),
        (ACCESS_API, "API"),
    )

    key = models.SlugField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=60, blank=True, default="apps")
    color = models.CharField(max_length=20, blank=True, default="#2563EB")
    web_url = models.CharField(max_length=240, blank=True, default="")
    app_route = models.CharField(max_length=120, blank=True, default="")
    api_namespace = models.CharField(max_length=120, blank=True, default="")
    access_platforms = models.JSONField(default=list, blank=True)
    required_permissions = models.JSONField(default=list, blank=True)
    settings = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=100, db_index=True)
    is_core = models.BooleanField(default=False, db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        indexes = [models.Index(fields=["is_enabled", "order"])]

    def __str__(self) -> str:
        return self.name


class PermissionTemplate(models.Model):
    """One-click permission preset backed by the existing SaaS PermissionNode graph."""

    key = models.SlugField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    role = models.ForeignKey("saas.RoleTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="enterprise_templates")
    permission_keys = models.JSONField(default=list, blank=True)
    platform_access = models.JSONField(default=dict, blank=True)
    is_system = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Workspace(models.Model):
    key = models.SlugField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    role = models.ForeignKey("saas.RoleTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="workspaces")
    landing_route = models.CharField(max_length=160, blank=True, default="")
    platform = models.CharField(max_length=30, blank=True, default="web")
    module_keys = models.JSONField(default=list, blank=True)
    menu_schema = models.JSONField(default=list, blank=True)
    layout_schema = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    order = models.PositiveIntegerField(default=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class UserWorkspace(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enterprise_workspace")
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_users")
    role = models.ForeignKey("saas.RoleTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_user_workspaces")
    platform_overrides = models.JSONField(default=dict, blank=True)
    module_overrides = models.JSONField(default=dict, blank=True)
    dashboard_overrides = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["role"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.workspace_id or 'auto'}"


class DashboardWidget(models.Model):
    TYPE_METRIC = "metric"
    TYPE_CHART = "chart"
    TYPE_TABLE = "table"
    TYPE_STATUS = "status"
    TYPE_ACTIONS = "actions"
    TYPE_CHOICES = (
        (TYPE_METRIC, "Metric"),
        (TYPE_CHART, "Chart"),
        (TYPE_TABLE, "Table"),
        (TYPE_STATUS, "Status"),
        (TYPE_ACTIONS, "Actions"),
    )

    key = models.SlugField(max_length=80, db_index=True)
    title = models.CharField(max_length=140)
    widget_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_METRIC)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, null=True, blank=True, related_name="widgets")
    module = models.ForeignKey(DynamicModule, on_delete=models.SET_NULL, null=True, blank=True, related_name="widgets")
    permission_key = models.CharField(max_length=120, blank=True, default="")
    data_source = models.CharField(max_length=160, blank=True, default="")
    config = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=100, db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["order", "title"]
        unique_together = ("workspace", "key")

    def __str__(self) -> str:
        return self.title


class DynamicButton(models.Model):
    """Runtime button/action rendered by admin, web, Flutter, POS, and kiosk shells."""

    SHAPE_CHOICES = (
        ("rounded", "Rounded"),
        ("square", "Square"),
        ("pill", "Pill"),
        ("circle", "Circle"),
    )
    ACTION_CHOICES = (
        ("route", "Open Route"),
        ("api", "Call API"),
        ("module", "Open Module"),
        ("report", "Open Report"),
        ("service", "Run Service"),
    )

    key = models.SlugField(max_length=90, unique=True, db_index=True)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    module = models.ForeignKey(DynamicModule, on_delete=models.SET_NULL, null=True, blank=True, related_name="buttons")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, null=True, blank=True, related_name="buttons")
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, default="route")
    route = models.CharField(max_length=180, blank=True, default="")
    api_endpoint = models.CharField(max_length=220, blank=True, default="")
    service_key = models.CharField(max_length=120, blank=True, default="")
    icon = models.CharField(max_length=60, blank=True, default="bolt")
    color = models.CharField(max_length=20, blank=True, default="#2563EB")
    gradient = models.JSONField(default=list, blank=True)
    shape = models.CharField(max_length=20, choices=SHAPE_CHOICES, default="rounded")
    animation = models.CharField(max_length=40, blank=True, default="smooth")
    permission_key = models.CharField(max_length=120, blank=True, default="")
    plan_keys = models.JSONField(default=list, blank=True)
    role_keys = models.JSONField(default=list, blank=True)
    platform_access = models.JSONField(default=list, blank=True)
    config = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=100, db_index=True)
    is_primary = models.BooleanField(default=False, db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "label"]
        indexes = [models.Index(fields=["is_enabled", "order"])]

    def __str__(self) -> str:
        return self.label


class DynamicMenuItem(models.Model):
    """Nested sidebar/menu node with drag-sort order and permission policy."""

    key = models.SlugField(max_length=90, unique=True, db_index=True)
    title = models.CharField(max_length=120)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, null=True, blank=True, related_name="menu_items")
    module = models.ForeignKey(DynamicModule, on_delete=models.SET_NULL, null=True, blank=True, related_name="menu_items")
    icon = models.CharField(max_length=60, blank=True, default="apps")
    route = models.CharField(max_length=180, blank=True, default="")
    badge = models.CharField(max_length=40, blank=True, default="")
    color = models.CharField(max_length=20, blank=True, default="#2563EB")
    permission_key = models.CharField(max_length=120, blank=True, default="")
    platform_access = models.JSONField(default=list, blank=True)
    config = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=100, db_index=True)
    is_group = models.BooleanField(default=False, db_index=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "title"]
        indexes = [models.Index(fields=["parent", "is_enabled", "order"])]

    def __str__(self) -> str:
        return self.title


class ThemeConfig(models.Model):
    key = models.SlugField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    brand_name = models.CharField(max_length=120, blank=True, default="Billentra")
    logo_url = models.CharField(max_length=300, blank=True, default="")
    primary = models.CharField(max_length=20, default="#0F766E")
    secondary = models.CharField(max_length=20, default="#2563EB")
    accent = models.CharField(max_length=20, default="#F59E0B")
    surface = models.CharField(max_length=20, default="#F8FAFC")
    dark_surface = models.CharField(max_length=20, default="#0B1120")
    radius = models.PositiveSmallIntegerField(default=8)
    density = models.CharField(max_length=20, default="comfortable")
    typography = models.JSONField(default=dict, blank=True)
    platform_overrides = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self) -> str:
        return self.name


class DeviceSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enterprise_device_sessions")
    device_id = models.CharField(max_length=120, db_index=True)
    platform = models.CharField(max_length=30, blank=True, default="")
    app_version = models.CharField(max_length=40, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    last_seen_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = ("user", "device_id")
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.device_id}"


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="enterprise_audit_logs")
    action = models.CharField(max_length=120, db_index=True)
    target = models.CharField(max_length=180, blank=True, default="")
    platform = models.CharField(max_length=30, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "created_at"])]

    def __str__(self) -> str:
        return f"{self.action}:{self.target}"


class EnterpriseSetting(models.Model):
    """Superadmin-controlled runtime settings for web, mobile, POS, kiosk, and integrations."""

    CATEGORY_CHOICES = (
        ("general", "General Settings"),
        ("api", "API Settings"),
        ("jwt", "JWT Settings"),
        ("app", "App Settings"),
        ("mobile", "Mobile Settings"),
        ("pos", "POS Settings"),
        ("kiosk", "Kiosk Settings"),
        ("branding", "Branding Settings"),
        ("smtp", "SMTP Settings"),
        ("whatsapp", "WhatsApp Settings"),
        ("sms", "SMS Settings"),
        ("ai", "AI Settings"),
        ("security", "Security Settings"),
        ("device", "Device Settings"),
    )
    DATA_TYPE_CHOICES = (
        ("string", "String"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("json", "JSON"),
        ("url", "URL"),
        ("secret", "Secret"),
    )

    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, db_index=True)
    key = models.SlugField(max_length=120, unique=True, db_index=True)
    label = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default="string")
    value = models.JSONField(default=dict, blank=True)
    default_value = models.JSONField(default=dict, blank=True)
    platform_access = models.JSONField(default=list, blank=True)
    is_secret = models.BooleanField(default=False, db_index=True)
    is_public = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="enterprise_control_setting_updates")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "key"]
        indexes = [models.Index(fields=["category", "is_active"])]

    def __str__(self) -> str:
        return f"{self.category}:{self.key}"


class APIRegistry(models.Model):
    """Central registry of Django/FastAPI APIs and their app connectivity status."""

    STATUS_CREATED = "created"
    STATUS_CONNECTED = "connected"
    STATUS_USED = "used"
    STATUS_NOT_CONNECTED = "not_connected"
    STATUS_FAILED = "failed"
    STATUS_PENDING = "pending"
    STATUS_TESTED = "tested"
    STATUS_ACTIVE = "active"
    STATUS_PARTIAL = "partial"
    STATUS_MISSING = "missing"
    STATUS_SYNCING = "syncing"
    STATUS_CHOICES = (
        (STATUS_CREATED, "Created"),
        (STATUS_CONNECTED, "Connected"),
        (STATUS_USED, "Used In App"),
        (STATUS_NOT_CONNECTED, "Not Connected"),
        (STATUS_FAILED, "Failed"),
        (STATUS_PENDING, "Pending"),
        (STATUS_TESTED, "Tested"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_PARTIAL, "Partial"),
        (STATUS_MISSING, "Missing"),
        (STATUS_SYNCING, "Syncing"),
    )
    METHOD_CHOICES = (
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("PATCH", "PATCH"),
        ("DELETE", "DELETE"),
        ("OPTIONS", "OPTIONS"),
    )

    name = models.CharField(max_length=180)
    endpoint = models.CharField(max_length=260, db_index=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default="GET", db_index=True)
    module = models.CharField(max_length=80, blank=True, default="", db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_CREATED, db_index=True)
    connected_apps = models.JSONField(default=list, blank=True)
    permission_keys = models.JSONField(default=list, blank=True)
    version = models.CharField(max_length=40, blank=True, default="v1")
    auth_required = models.BooleanField(default=True, db_index=True)
    source = models.CharField(max_length=40, blank=True, default="manual", db_index=True)
    last_usage_at = models.DateTimeField(null=True, blank=True)
    last_response_status = models.PositiveIntegerField(null=True, blank=True)
    last_response_time_ms = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module", "endpoint", "method"]
        unique_together = ("endpoint", "method")
        verbose_name = "API Registry"
        verbose_name_plural = "API Registry"

    def __str__(self) -> str:
        return f"{self.method} {self.endpoint}"


class APITestLog(models.Model):
    api = models.ForeignKey(APIRegistry, on_delete=models.CASCADE, related_name="test_logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="api_test_logs")
    request_payload = models.JSONField(default=dict, blank=True)
    request_headers = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    response_text = models.TextField(blank=True, default="")
    status_code = models.PositiveIntegerField(default=0, db_index=True)
    response_time_ms = models.PositiveIntegerField(default=0)
    auth_status = models.CharField(max_length=40, blank=True, default="")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.api} -> {self.status_code}"


class AppFeatureMapping(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("missing", "Missing"),
        ("partial", "Partial"),
        ("pending", "Pending"),
        ("failed", "Failed"),
    )

    feature_key = models.SlugField(max_length=120, unique=True, db_index=True)
    feature_name = models.CharField(max_length=160)
    module = models.ForeignKey(DynamicModule, on_delete=models.SET_NULL, null=True, blank=True, related_name="feature_mappings")
    description = models.TextField(blank=True, default="")
    required_apis = models.JSONField(default=list, blank=True)
    connected_apis = models.ManyToManyField(APIRegistry, blank=True, related_name="feature_mappings")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    platforms = models.JSONField(default=list, blank=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["feature_name"]

    def __str__(self) -> str:
        return self.feature_name
