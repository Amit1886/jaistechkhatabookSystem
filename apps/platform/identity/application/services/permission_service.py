from django.utils import timezone

from apps.platform.identity.infrastructure.repositories.identity_repository import IdentityRepository


class PermissionDecision:
    def __init__(self, allowed: bool, reason: str = ""):
        self.allowed = allowed
        self.reason = reason

    def __bool__(self):
        return self.allowed


class PermissionService:
    def __init__(self, repository=None):
        self.repository = repository or IdentityRepository()

    def has_permission(self, user, key: str, *, tenant=None) -> PermissionDecision:
        if not getattr(user, "is_authenticated", False):
            return PermissionDecision(False, "anonymous")
        if not user.is_active:
            return PermissionDecision(False, "inactive_user")
        if user.is_superuser or user.is_staff:
            return PermissionDecision(True, "staff_or_superuser")

        key = (key or "").strip()
        if not key:
            return PermissionDecision(False, "empty_permission")

        permission = self.repository.permission_for_key(tenant=tenant, key=key)
        override = self.repository.user_override(tenant=tenant, user=user, permission=permission)
        if override and override.is_current():
            return PermissionDecision(bool(override.allowed), "user_override")

        role_allowed = self.repository.role_permission_allowed(tenant=tenant, user=user, permission=permission)
        if role_allowed is not None:
            return PermissionDecision(bool(role_allowed), "role_permission")

        try:
            if hasattr(user, "has_permission") and user.has_permission(key):
                return PermissionDecision(True, "legacy_user_permission")
        except Exception:
            pass

        # Backward compatible default: undefined enterprise permission does not
        # block existing screens until admins configure the matrix.
        if permission is None:
            return PermissionDecision(True, "undefined_enterprise_permission")
        return PermissionDecision(False, "permission_denied")

    def field_access(self, user, field_key: str, *, tenant=None, default="write"):
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return "write"
        access = self.repository.field_access(tenant=tenant, user=user, field_key=field_key)
        return access or default

    def within_time_window(self, user, now=None):
        now = now or timezone.now()
        try:
            restrictions = (getattr(user, "permissions_json", None) or {}).get("time_windows", {})
            if not restrictions:
                return PermissionDecision(True, "no_time_restriction")
            weekday = str(now.weekday())
            windows = restrictions.get(weekday, [])
            current = now.strftime("%H:%M")
            for start, end in windows:
                if start <= current <= end:
                    return PermissionDecision(True, "inside_time_window")
            return PermissionDecision(False, "outside_time_window")
        except Exception:
            return PermissionDecision(True, "time_window_unreadable")
