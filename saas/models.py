from __future__ import annotations

from django.db import models


# ---------------- Multi-tenancy (django-tenants blueprint) ----------------
# Phase A (safe): keep multi-tenancy disabled at DB/schema level.
# Phase B: enable django-tenants + PostgreSQL and then turn these models on.
try:
    from django_tenants.models import DomainMixin, TenantMixin  # type: ignore
except Exception:  # pragma: no cover
    DomainMixin = None  # type: ignore
    TenantMixin = None  # type: ignore


if TenantMixin is not None and DomainMixin is not None:
    class SellerTenant(TenantMixin):  # type: ignore[misc]
        """
        Seller tenant. Each seller -> separate schema (Postgres).
        """

        name = models.CharField(max_length=200)
        subdomain = models.SlugField(max_length=63, unique=True, db_index=True)
        is_active = models.BooleanField(default=True, db_index=True)
        created_at = models.DateTimeField(auto_now_add=True)

        auto_create_schema = True

        class Meta:
            app_label = "saas"
            verbose_name = "Seller Tenant"
            verbose_name_plural = "Seller Tenants"

        def __str__(self):
            return f"{self.name} ({self.subdomain})"


    class SellerDomain(DomainMixin):  # type: ignore[misc]
        class Meta:
            app_label = "saas"
            verbose_name = "Seller Domain"
            verbose_name_plural = "Seller Domains"


# ---------------- RBAC ----------------
class PermissionMaster(models.Model):
    """
    Central registry of permissions (key -> label).
    """

    key = models.SlugField(max_length=120, unique=True, db_index=True)
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    module = models.CharField(max_length=80, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = "saas"
        ordering = ["module", "key"]

    def __str__(self):
        return self.key


class Role(models.Model):
    key = models.SlugField(max_length=80, unique=True, db_index=True)
    label = models.CharField(max_length=120)
    is_system = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = "saas"
        ordering = ["key"]

    def __str__(self):
        return self.key


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(PermissionMaster, on_delete=models.CASCADE, related_name="role_permissions")

    class Meta:
        app_label = "saas"
        unique_together = ("role", "permission")

    def __str__(self):
        return f"{self.role_id}:{self.permission_id}"


# ---------------- APGS (Advanced Permission Graph System) ----------------
class Department(models.Model):
    """
    Department groups permissions/roles for large org setups.
    """

    key = models.SlugField(max_length=60, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = "saas"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class PermissionNode(models.Model):
    """
    Permission tree node (supports hierarchical keys like `order.create`).
    """

    key = models.SlugField(max_length=120, unique=True, db_index=True)
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    module = models.CharField(max_length=80, blank=True, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="permissions")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = "saas"
        ordering = ["module", "key"]

    def __str__(self) -> str:
        return self.key


class RoleTemplate(models.Model):
    """
    Role template defines a reusable permission set.
    """

    key = models.SlugField(max_length=80, unique=True, db_index=True)
    label = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="roles")
    is_system = models.BooleanField(default=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        app_label = "saas"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class RoleTemplatePermission(models.Model):
    EFFECT_ALLOW = "allow"
    EFFECT_DENY = "deny"
    EFFECT_CHOICES = (
        (EFFECT_ALLOW, "Allow"),
        (EFFECT_DENY, "Deny"),
    )

    role = models.ForeignKey(RoleTemplate, on_delete=models.CASCADE, related_name="role_edges")
    permission = models.ForeignKey(PermissionNode, on_delete=models.CASCADE, related_name="role_edges")
    effect = models.CharField(max_length=10, choices=EFFECT_CHOICES, default=EFFECT_ALLOW, db_index=True)

    class Meta:
        app_label = "saas"
        unique_together = ("role", "permission")

    def __str__(self) -> str:
        return f"{self.role_id}:{self.permission_id}:{self.effect}"


class UserPermissionGraph(models.Model):
    """
    User -> role templates + overrides (allow/deny) + inheritance.

    Phase A tenant isolation:
    - scope by `seller_id` (Vendor) when present.
    """

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="permission_graphs")
    role = models.ForeignKey(RoleTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="user_graphs")
    seller = models.ForeignKey("vendors.Vendor", on_delete=models.SET_NULL, null=True, blank=True, related_name="user_permission_graphs")
    inherit_from_owner = models.BooleanField(default=True, db_index=True)
    overrides_json = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "saas"
        indexes = [models.Index(fields=["user", "seller", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.role_id or 'no-role'}"


class UserPermissionOverride(models.Model):
    """
    No-code per-user permission toggles.

    This is the APGS equivalent of `billing.UserFeatureOverride`:
    - Every active PermissionNode can appear here automatically.
    - Admin can allow/deny without writing code.
    """

    EFFECT_ALLOW = "allow"
    EFFECT_DENY = "deny"
    EFFECT_NONE = "none"
    EFFECT_CHOICES = (
        (EFFECT_ALLOW, "Allow"),
        (EFFECT_DENY, "Deny"),
        (EFFECT_NONE, "Inherit"),
    )

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="permission_overrides")
    seller = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_permission_overrides",
        help_text="Optional per-vendor override scope (Phase A tenancy).",
    )
    permission = models.ForeignKey(PermissionNode, on_delete=models.CASCADE, related_name="user_overrides")
    effect = models.CharField(max_length=10, choices=EFFECT_CHOICES, default=EFFECT_NONE, db_index=True)
    note = models.CharField(max_length=200, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "saas"
        unique_together = ("user", "seller", "permission")
        indexes = [models.Index(fields=["user", "seller", "effect"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.permission_id}:{self.effect}"
