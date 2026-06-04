from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import (
    PermissionMaster,
    PermissionNode,
    Role,
    RolePermission,
    RoleTemplate,
    RoleTemplatePermission,
)
from .utils.permissions import require_permission


@login_required
@require_permission("tenant_create")
@require_http_methods(["GET", "POST"])
def tenant_create_view(request):
    """
    Blueprint: tenant creation flow.

    In production with django-tenants:
    - Create SellerTenant + SellerDomain
    - Provision schema
    - Bootstrap default roles/permissions
    """
    return JsonResponse(
        {
            "ok": True,
            "mode": "phase_a",
            "message": "Tenant provisioning is disabled in Phase A. Enable django-tenants + PostgreSQL in Phase B.",
        }
    )


@login_required
@require_permission("rbac_view")
@require_http_methods(["GET"])
def rbac_registry_view(request):
    """
    Backend-only endpoint for debugging RBAC state without adding templates.
    """
    perms = list(PermissionMaster.objects.filter(is_active=True).values("key", "label", "module"))
    try:
        apgs_perms = list(PermissionNode.objects.filter(is_active=True).values("key", "label", "module"))
    except Exception:
        apgs_perms = []
    roles = list(Role.objects.filter(is_active=True).values("key", "label", "is_system"))
    try:
        role_templates = list(RoleTemplate.objects.filter(is_active=True).values("key", "label", "is_system"))
    except Exception:
        role_templates = []
    role_perms = list(
        RolePermission.objects.select_related("role", "permission")
        .values("role__key", "permission__key")
        .order_by("role__key", "permission__key")
    )
    try:
        apgs_role_edges = list(
            RoleTemplatePermission.objects.select_related("role", "permission")
            .values("role__key", "permission__key", "effect")
            .order_by("role__key", "permission__key")
        )
    except Exception:
        apgs_role_edges = []
    return JsonResponse(
        {
            "ok": True,
            "permissions": perms,
            "roles": roles,
            "role_permissions": role_perms,
            "apgs_permissions": apgs_perms,
            "apgs_roles": role_templates,
            "apgs_role_edges": apgs_role_edges,
        }
    )
