from __future__ import annotations

from typing import Any, Dict

from saas.utils.permissions import user_has_permission


def tenant_info(request) -> Dict[str, Any]:
    """
    Generic tenant info for templates.

    IMPORTANT: The project currently uses subdomain resolution via `vendors.middleware.VendorSubdomainMiddleware`.
    When migrating to django-tenants, request.tenant will exist.
    """
    tenant = getattr(request, "tenant", None)
    vendor_subdomain = getattr(request, "vendor_subdomain", "")
    return {
        "tenant": tenant,
        "tenant_schema": getattr(tenant, "schema_name", None),
        "tenant_subdomain": getattr(tenant, "subdomain", None) if tenant else (vendor_subdomain or ""),
    }


def user_permissions(request) -> Dict[str, Any]:
    user = getattr(request, "user", None)
    perms = {}
    has_perm = getattr(user, "has_permission", None)
    if callable(has_perm):
        try:
            perms = dict(getattr(user, "permissions_json", None) or {})
        except Exception:
            perms = {}
    return {"user_permissions": perms}


def subscription_info(request) -> Dict[str, Any]:
    """
    Expose subscription/plan info for templates without enforcing UI changes.

    Phase A source of truth is `billing.services` (FeatureRegistry + PlanFeature).
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"plan": None, "locked_feature_count": None}
    try:
        from billing.services import get_effective_plan, get_locked_feature_count

        return {
            "plan": get_effective_plan(user),
            "locked_feature_count": get_locked_feature_count(user),
        }
    except Exception:
        return {"plan": None, "locked_feature_count": None}


def feature_flags(request) -> Dict[str, Any]:
    """
    Backend-only flags used by templates to hide/show actions.

    Templates may already contain `{% if ... %}` checks; adding these keys is non-breaking.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {
            "can_create_order": False,
            "can_access_warehouse": False,
            "can_access_reports": False,
            "can_access_vendor_panel": False,
            "can_post_ledger": False,
        }

    # Primary permissions (support both dotted and underscored keys at call-site)
    can_create_order = user_has_permission(user, "order.create") or user_has_permission(user, "create_order")
    can_access_warehouse = any(
        user_has_permission(user, k)
        for k in ("warehouse.access", "stock_inward", "stock_outward", "stock_adjust")
    )
    can_post_ledger = any(user_has_permission(user, k) for k in ("ledger.post", "ledger_post", "payment_record"))
    can_access_vendor_panel = any(user_has_permission(user, k) for k in ("vendor_access", "store_settings"))
    can_access_reports = user_has_permission(user, "view_reports") or user_has_permission(user, "reports.view")

    return {
        "can_create_order": can_create_order,
        "can_access_warehouse": can_access_warehouse,
        "can_access_reports": can_access_reports,
        "can_access_vendor_panel": can_access_vendor_panel,
        "can_post_ledger": can_post_ledger,
    }


def cart_count(request) -> Dict[str, Any]:
    """
    Blueprint placeholder: implement using your existing cart/session service.
    """
    try:
        cart = getattr(request, "cart", None)
        if cart and isinstance(cart, dict):
            return {"cart_count": int(cart.get("total_qty") or 0)}
    except Exception:
        pass
    return {"cart_count": 0}


def order_count(request) -> Dict[str, Any]:
    """
    Blueprint placeholder: implement per-tenant order count caching.
    """
    return {"order_count": None}
