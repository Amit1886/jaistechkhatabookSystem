import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Tenant(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_tenants")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "tenants"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Company(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="companies")
    name = models.CharField(max_length=180)
    legal_name = models.CharField(max_length=220, blank=True, default="")
    gst_number = models.CharField(max_length=32, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "companies"
        unique_together = ("tenant", "name")
        ordering = ("tenant__name", "name")

    def __str__(self):
        return self.name


class Branch(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="branches")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=40, db_index=True)
    address = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "branches"
        unique_together = ("tenant", "code")
        ordering = ("company__name", "name")

    def __str__(self):
        return f"{self.company} / {self.name}"


class TenantMembership(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships")
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_memberships")
    is_active = models.BooleanField(default=True, db_index=True)
    is_owner = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "tenant_memberships"
        unique_together = ("tenant", "user")

    def __str__(self):
        return f"{self.user} @ {self.tenant}"


class DynamicModule(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="dynamic_modules")
    key = models.CharField(max_length=140, db_index=True)
    label = models.CharField(max_length=180)
    app_label = models.CharField(max_length=120, blank=True, default="")
    route_name = models.CharField(max_length=180, blank=True, default="")
    menu_key = models.CharField(max_length=140, blank=True, default="", db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "dynamic_modules"
        unique_together = ("tenant", "key")
        ordering = ("key",)

    def __str__(self):
        return self.label


class DynamicField(TimestampedModel):
    module = models.ForeignKey(DynamicModule, on_delete=models.CASCADE, related_name="fields")
    key = models.CharField(max_length=140)
    label = models.CharField(max_length=180)
    model_path = models.CharField(max_length=240, blank=True, default="")
    field_name = models.CharField(max_length=140, blank=True, default="")
    is_sensitive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "dynamic_fields"
        unique_together = ("module", "key")
        ordering = ("module__key", "key")

    def __str__(self):
        return f"{self.module.key}.{self.key}"


class EnterpriseRole(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="roles")
    name = models.CharField(max_length=160)
    key = models.SlugField(max_length=160, db_index=True)
    description = models.TextField(blank=True, default="")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "roles"
        unique_together = ("tenant", "key")
        ordering = ("tenant__name", "name")

    def __str__(self):
        return self.name


class EnterprisePermission(TimestampedModel):
    class Scope(models.TextChoices):
        MODULE = "module", "Module"
        MENU = "menu", "Menu"
        ACTION = "action", "Action"
        FIELD = "field", "Field"
        API = "api", "API"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="permissions")
    module = models.ForeignKey(DynamicModule, on_delete=models.SET_NULL, null=True, blank=True, related_name="permissions")
    key = models.CharField(max_length=180, db_index=True)
    label = models.CharField(max_length=220)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.ACTION, db_index=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "permissions"
        unique_together = ("tenant", "key")
        ordering = ("key",)

    def __str__(self):
        return self.key


class RolePermission(TimestampedModel):
    role = models.ForeignKey(EnterpriseRole, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(EnterprisePermission, on_delete=models.CASCADE, related_name="role_permissions")
    allowed = models.BooleanField(default=True)
    conditions = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "role_permissions"
        unique_together = ("role", "permission")

    def __str__(self):
        return f"{self.role} -> {self.permission}"


class FieldPermission(TimestampedModel):
    class Access(models.TextChoices):
        HIDDEN = "hidden", "Hidden"
        READ = "read", "Read"
        WRITE = "write", "Write"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="field_permissions")
    role = models.ForeignKey(EnterpriseRole, on_delete=models.CASCADE, null=True, blank=True, related_name="field_permissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="field_permissions")
    field = models.ForeignKey(DynamicField, on_delete=models.CASCADE, related_name="field_permissions")
    access = models.CharField(max_length=20, choices=Access.choices, default=Access.READ)

    class Meta:
        db_table = "field_permissions"
        indexes = [models.Index(fields=["tenant", "user", "role"])]

    def clean(self):
        if not self.role_id and not self.user_id:
            raise ValidationError("Field permission requires role or user.")


class PermissionOverride(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="permission_overrides")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enterprise_permission_overrides")
    permission = models.ForeignKey(EnterprisePermission, on_delete=models.CASCADE, related_name="permission_overrides")
    allowed = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_permission_overrides")

    class Meta:
        db_table = "permission_overrides"
        unique_together = ("tenant", "user", "permission")

    def is_current(self):
        now = timezone.now()
        return (self.starts_at is None or self.starts_at <= now) and (self.expires_at is None or self.expires_at >= now)


class UserDevice(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        TRUSTED = "trusted", "Trusted"
        BLOCKED = "blocked", "Blocked"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="user_devices")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enterprise_devices")
    fingerprint = models.CharField(max_length=220, db_index=True)
    name = models.CharField(max_length=180, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "user_devices"
        unique_together = ("tenant", "user", "fingerprint")


class ActivitySession(TimestampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="activity_sessions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_sessions")
    session_key = models.CharField(max_length=80, db_index=True)
    device = models.ForeignKey(UserDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="activity_sessions")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "activity_sessions"
        indexes = [models.Index(fields=["tenant", "user", "is_active"])]


class LoginHistory(TimestampedModel):
    class Result(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        BLOCKED = "blocked", "Blocked"

    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_history")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_history")
    email = models.EmailField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    result = models.CharField(max_length=20, choices=Result.choices, db_index=True)
    reason = models.CharField(max_length=240, blank=True, default="")
    device = models.ForeignKey(UserDevice, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_history")

    class Meta:
        db_table = "login_history"
        ordering = ("-created_at",)


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    action = models.CharField(max_length=180, db_index=True)
    actor_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    object_type = models.CharField(max_length=180, blank=True, default="", db_index=True)
    object_id = models.CharField(max_length=180, blank=True, default="", db_index=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit logs are immutable.")
        return super().save(*args, **kwargs)


class VersionHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="version_history")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="version_history")
    object_type = models.CharField(max_length=180, db_index=True)
    object_id = models.CharField(max_length=180, db_index=True)
    version = models.PositiveIntegerField(default=1)
    snapshot = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "version_history"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["object_type", "object_id", "version"])]


class SmartNotification(TimestampedModel):
    class Status(models.TextChoices):
        UNREAD = "unread", "Unread"
        READ = "read", "Read"
        ARCHIVED = "archived", "Archived"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="smart_notifications")
    title = models.CharField(max_length=220)
    message = models.TextField(blank=True, default="")
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNREAD, db_index=True)
    action_url = models.CharField(max_length=500, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ("-created_at",)
