from __future__ import annotations

from django.db import transaction
from django.db.models import Q

from saas.models import PermissionNode, UserPermissionOverride


@transaction.atomic
def ensure_user_permission_overrides(user, *, seller=None) -> dict:
    """
    Ensure every active PermissionNode appears for the user as a toggle row.

    This enables the required no-code behavior:
    - new permission nodes automatically appear in admin panel
    - admin can allow/deny without any code changes
    """
    if not user or not getattr(user, "is_authenticated", False):
        return {"created": 0}

    seller_id = getattr(seller, "id", None) if seller is not None else getattr(user, "seller_id", None)
    created = 0

    existing = set(
        UserPermissionOverride.objects.filter(user=user)
        .filter(Q(seller_id=seller_id) | Q(seller__isnull=True))
        .values_list("permission_id", flat=True)
    )
    for p in PermissionNode.objects.filter(is_active=True):
        if p.id in existing:
            continue
        UserPermissionOverride.objects.create(user=user, seller_id=seller_id, permission=p, effect=UserPermissionOverride.EFFECT_NONE, note="auto")
        created += 1
    return {"created": created}

