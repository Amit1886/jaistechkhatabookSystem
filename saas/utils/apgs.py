from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Set

from django.core.cache import cache
from django.db.models import Q

from saas.models import (
    RoleTemplate,
    RoleTemplatePermission,
    UserPermissionGraph,
    UserPermissionOverride,
)


@dataclass(frozen=True)
class _PermSet:
    allow: Set[str]
    deny: Set[str]


def _normalize_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        return ""
    # Canonical storage-friendly key.
    if not (k.startswith("feature.") or k.startswith("feature:")) and "." in k:
        k = k.replace(".", "_")
    return k


def _extract_overrides(overrides_json: object) -> tuple[Set[str], Set[str]]:
    allow: Set[str] = set()
    deny: Set[str] = set()
    if not overrides_json:
        return allow, deny

    # Supported shapes:
    # 1) {"allow": [...], "deny": [...]}
    # 2) {"order_create": true, "ledger_post": false}
    # 3) {"order_create": "allow", "ledger_post": "deny"}
    if isinstance(overrides_json, dict):
        if isinstance(overrides_json.get("allow"), (list, tuple, set)):
            allow |= {_normalize_key(x) for x in overrides_json.get("allow") if _normalize_key(str(x))}
        if isinstance(overrides_json.get("deny"), (list, tuple, set)):
            deny |= {_normalize_key(x) for x in overrides_json.get("deny") if _normalize_key(str(x))}
        for k, v in overrides_json.items():
            if k in {"allow", "deny"}:
                continue
            kk = _normalize_key(str(k))
            if not kk:
                continue
            if v in {True, 1, "1", "true", "yes", "on", "allow"}:
                allow.add(kk)
            if v in {False, 0, "0", "false", "no", "off", "deny"}:
                deny.add(kk)
    return allow, deny


def _build_permset_for_user(user, *, seller_id: Optional[int], depth: int = 0) -> _PermSet:
    if not user or not getattr(user, "is_authenticated", False):
        return _PermSet(set(), set())

    cache_key = f"apgs:permset:u{user.id}:s{seller_id or 0}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict) and "allow" in cached and "deny" in cached:
        return _PermSet(set(cached["allow"]), set(cached["deny"]))

    allow: Set[str] = set()
    deny: Set[str] = set()

    # Active graphs for this seller or global (seller is NULL).
    graphs = (
        UserPermissionGraph.objects.filter(user=user, is_active=True)
        .filter(Q(seller_id=seller_id) | Q(seller__isnull=True))
        .select_related("role")
        .order_by("-id")
    )

    # Attach a role by `primary_role` if admin hasn't created a graph row.
    primary_role = (getattr(user, "primary_role", "") or "").strip().lower()
    if primary_role:
        rt = RoleTemplate.objects.filter(key=primary_role, is_active=True).first()
        if rt:
            allow.add(f"__role__:{rt.id}")  # marker

    # Role edges
    role_ids: Set[int] = {g.role_id for g in graphs if g.role_id}  # type: ignore[arg-type]
    # marker role from primary_role
    for marker in list(allow):
        if marker.startswith("__role__:"):
            try:
                role_ids.add(int(marker.split(":", 1)[1]))
            except Exception:
                pass
            allow.discard(marker)

    if role_ids:
        edges = (
            RoleTemplatePermission.objects.filter(role_id__in=list(role_ids))
            .select_related("permission")
            .only("effect", "permission__key")
        )
        for e in edges:
            key = _normalize_key(getattr(e.permission, "key", ""))
            if not key:
                continue
            if e.effect == RoleTemplatePermission.EFFECT_DENY:
                deny.add(key)
            else:
                allow.add(key)

    # Overrides (deny wins)
    for g in graphs:
        a2, d2 = _extract_overrides(getattr(g, "overrides_json", None))
        allow |= a2
        deny |= d2

    # No-code row-based overrides (stronger than JSON overrides; deny wins)
    try:
        row_overrides = (
            UserPermissionOverride.objects.filter(user=user)
            .filter(Q(seller_id=seller_id) | Q(seller__isnull=True))
            .select_related("permission")
        )
        for row in row_overrides:
            k = _normalize_key(getattr(row.permission, "key", ""))
            if not k:
                continue
            if row.effect == UserPermissionOverride.EFFECT_DENY:
                deny.add(k)
            elif row.effect == UserPermissionOverride.EFFECT_ALLOW:
                allow.add(k)
    except Exception:
        pass

    # Inheritance from owner/parent (single level, safe recursion guard)
    if depth < 1:
        inherit = graphs.filter(inherit_from_owner=True).exists()
        parent = getattr(user, "parent", None)
        if inherit and parent:
            parent_set = _build_permset_for_user(parent, seller_id=seller_id, depth=depth + 1)
            allow |= parent_set.allow
            deny |= parent_set.deny

    # Deny precedence
    allow -= deny

    cache.set(cache_key, {"allow": list(allow), "deny": list(deny)}, 30)
    return _PermSet(allow=allow, deny=deny)


def apgs_has_permission(user, key: str, *, seller_id: Optional[int] = None) -> bool:
    """
    Advanced permission resolver.

    - Canonical keys (underscored) are stored and compared.
    - Dotted keys may be used by callers and are normalized.
    """
    k = _normalize_key(key)
    if not k:
        return False

    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True

    if (getattr(user, "primary_role", "") or "").strip().lower() == "owner":
        return True

    sid = seller_id
    if sid is None:
        sid = getattr(user, "seller_id", None)

    permset = _build_permset_for_user(user, seller_id=sid)
    if k in permset.deny:
        return False
    if k in permset.allow:
        return True

    # Parent-key wildcarding: if role grants `order` then allow `order_create`, etc.
    # (Simple heuristic; keeps storage slug-safe.)
    prefix = k.split("_", 1)[0]
    if prefix and prefix in permset.allow and prefix not in permset.deny:
        return True
    return False
