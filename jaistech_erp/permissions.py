from rest_framework.permissions import BasePermission


class HasDynamicPermission(BasePermission):
    """
    Central runtime RBAC hook.

    Superusers pass automatically. Other users are checked against role/module
    grants stored in JaisTech ERP, then against the legacy User.has_permission
    helper when present.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True

        action = getattr(view, "action", request.method.lower())
        model = getattr(getattr(view, "queryset", None), "model", None)
        module_key = getattr(view, "module_key", "") or (model._meta.model_name if model else "")
        permission_key = f"{module_key}.{action}"

        try:
            from .models import UserBusinessMembership

            memberships = UserBusinessMembership.objects.filter(user=user, is_active=True).select_related("role")
            if memberships.filter(role__is_admin=True).exists():
                return True
            if memberships.filter(role__permissions__module__key=module_key, role__permissions__action=action).exists():
                return True
        except Exception:
            pass

        checker = getattr(user, "has_permission", None)
        if callable(checker):
            return bool(checker(permission_key) or checker(permission_key.replace(".", "_")))
        return False

