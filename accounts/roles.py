from __future__ import annotations

from enum import IntEnum


class Role(IntEnum):
    USER = 10
    AGENT = 20
    ADMIN = 30
    SUPER_ADMIN = 40


GROUP_TO_ROLE: dict[str, Role] = {
    "user": Role.USER,
    "agent": Role.AGENT,
    "admin": Role.ADMIN,
    "super admin": Role.SUPER_ADMIN,
    "superadmin": Role.SUPER_ADMIN,
}


def get_user_role(user) -> Role:
    """
    Resolve the effective ERP role.

    Safety default:
    - If no group role is assigned, default to ADMIN so existing single-user flows
      continue to work without locking users out.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return Role.USER

    if getattr(user, "is_superuser", False):
        return Role.SUPER_ADMIN

    # Prefer persisted SaaS role (if present) over groups for predictable behavior.
    saas_role = (getattr(user, "role", "") or "").strip().lower()
    if saas_role == "super_admin":
        return Role.SUPER_ADMIN
    if saas_role in {"state_admin", "district_admin", "area_admin"}:
        return Role.ADMIN
    if saas_role in {"super_agent", "agent"}:
        return Role.AGENT
    if saas_role == "customer":
        return Role.USER

    # Group-based role mapping (case-insensitive)
    for g in user.groups.all():
        key = (g.name or "").strip().lower()
        role = GROUP_TO_ROLE.get(key)
        if role:
            return role

    # Staff defaults to admin privileges in most ERP screens
    if getattr(user, "is_staff", False):
        return Role.ADMIN

    return Role.ADMIN


def can_view(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def can_edit(user) -> bool:
    return get_user_role(user) >= Role.AGENT


def can_delete(user) -> bool:
    return get_user_role(user) >= Role.ADMIN
