from __future__ import annotations

from django.db import OperationalError, ProgrammingError
from django.utils import timezone

from apps.platform.identity.models import (
    ActivitySession,
    AuditLog,
    EnterprisePermission,
    FieldPermission,
    LoginHistory,
    PermissionOverride,
    RolePermission,
    SmartNotification,
    Tenant,
    TenantMembership,
    UserDevice,
)


DB_NOT_READY = (OperationalError, ProgrammingError)


class IdentityRepository:
    def resolve_tenant_for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return None
        try:
            membership = (
                TenantMembership.objects.filter(user=user, is_active=True, tenant__status=Tenant.Status.ACTIVE)
                .select_related("tenant")
                .order_by("-is_owner", "-created_at")
                .first()
            )
            return membership.tenant if membership else None
        except DB_NOT_READY:
            return None

    def get_membership(self, *, tenant, user):
        if not tenant or not getattr(user, "is_authenticated", False):
            return None
        try:
            return TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).first()
        except DB_NOT_READY:
            return None

    def permission_for_key(self, *, tenant, key):
        try:
            return (
                EnterprisePermission.objects.filter(key=key, is_active=True)
                .filter(tenant__isnull=True if tenant is None else False)
                .first()
                or EnterprisePermission.objects.filter(tenant=tenant, key=key, is_active=True).first()
            )
        except DB_NOT_READY:
            return None

    def user_override(self, *, tenant, user, permission):
        if not permission:
            return None
        try:
            return PermissionOverride.objects.filter(tenant=tenant, user=user, permission=permission).first()
        except DB_NOT_READY:
            return None

    def role_permission_allowed(self, *, tenant, user, permission):
        if not permission:
            return None
        try:
            role_ids = TenantMembership.objects.filter(tenant=tenant, user=user, is_active=True).values_list(
                "metadata__role_id", flat=True
            )
            role_ids = [role_id for role_id in role_ids if role_id]
            if not role_ids:
                return None
            row = RolePermission.objects.filter(role_id__in=role_ids, permission=permission).first()
            return row.allowed if row else None
        except DB_NOT_READY:
            return None

    def field_access(self, *, tenant, user, field_key):
        try:
            rows = FieldPermission.objects.filter(field__key=field_key).select_related("field")
            if tenant:
                rows = rows.filter(tenant=tenant)
            user_row = rows.filter(user=user).first()
            if user_row:
                return user_row.access
            return None
        except DB_NOT_READY:
            return None

    def upsert_activity_session(self, *, tenant, user, session_key, ip_address, user_agent, device=None):
        if not session_key or not getattr(user, "is_authenticated", False):
            return None
        try:
            obj, _ = ActivitySession.objects.update_or_create(
                session_key=session_key,
                user=user,
                defaults={
                    "tenant": tenant,
                    "ip_address": ip_address,
                    "user_agent": user_agent[:2000],
                    "device": device,
                    "last_seen_at": timezone.now(),
                    "is_active": True,
                },
            )
            return obj
        except DB_NOT_READY:
            return None

    def get_or_create_device(self, *, tenant, user, fingerprint, ip_address, user_agent):
        if not fingerprint or not getattr(user, "is_authenticated", False):
            return None
        try:
            obj, _ = UserDevice.objects.get_or_create(
                tenant=tenant,
                user=user,
                fingerprint=fingerprint,
                defaults={"ip_address": ip_address, "user_agent": user_agent[:2000], "last_seen_at": timezone.now()},
            )
            UserDevice.objects.filter(pk=obj.pk).update(last_seen_at=timezone.now(), ip_address=ip_address)
            return obj
        except DB_NOT_READY:
            return None

    def create_audit_log(self, **kwargs):
        try:
            return AuditLog.objects.create(**kwargs)
        except DB_NOT_READY:
            return None

    def create_login_history(self, **kwargs):
        try:
            return LoginHistory.objects.create(**kwargs)
        except DB_NOT_READY:
            return None

    def notify(self, **kwargs):
        try:
            return SmartNotification.objects.create(**kwargs)
        except DB_NOT_READY:
            return None
