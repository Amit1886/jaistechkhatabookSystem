from __future__ import annotations

from django.contrib.auth.models import AnonymousUser


class PermissionEngine:
    """Central authorization policy for dynamic APIs and metadata."""

    def can_model_action(self, *, user, model, action: str) -> bool:
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        codename = f"{model._meta.app_label}.{action}_{model._meta.model_name}"
        return user.has_perm(codename)

    def can_view_metadata(self, *, user) -> bool:
        return bool(user and user.is_authenticated)


permission_engine = PermissionEngine()
