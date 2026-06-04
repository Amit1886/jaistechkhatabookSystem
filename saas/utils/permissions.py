from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

from django.core.exceptions import PermissionDenied


def user_has_permission(user, key: str) -> bool:
    """
    Unified permission check that works with the existing `accounts.User` model
    and the requested JSON-based RBAC extension.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    # Preferred: JSON RBAC
    has_perm = getattr(user, "has_permission", None)
    if callable(has_perm):
        try:
            return bool(has_perm(key))
        except Exception:
            pass

    # Fallback: Django permissions/groups
    try:
        return user.has_perm(key) or user.groups.filter(name=key).exists()
    except Exception:
        return False


def require_permission(key: str, *, message: Optional[str] = None) -> Callable:
    """
    Decorator for Django views.

    Usage:
        @require_permission("create_order")
        def my_view(...):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not user_has_permission(getattr(request, "user", None), key):
                raise PermissionDenied(message or f"Missing permission: {key}")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator

