from __future__ import annotations

from accounts.roles import can_delete, can_edit, get_user_role


def erp_role_context(request):
    user = getattr(request, "user", None)
    role = get_user_role(user)
    return {
        "erp_role": role.name.lower(),
        "erp_can_edit": can_edit(user),
        "erp_can_delete": can_delete(user),
    }

