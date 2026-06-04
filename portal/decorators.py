from __future__ import annotations

from functools import wraps
from typing import Callable, Optional

from django.contrib import messages
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from portal.models import PortalUser


def _extract_token(auth_header: str | None) -> str:
    if not auth_header:
        return ""
    auth_header = auth_header.strip()
    if auth_header.lower().startswith("token "):
        return auth_header[6:].strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return auth_header


def get_portal_user_from_session(request: HttpRequest) -> Optional[PortalUser]:
    pid = request.session.get("portal_user_id")
    if not pid:
        return None
    try:
        pu = (
            PortalUser.objects.select_related("party", "owner")
            .prefetch_related("permissions")
            .filter(id=int(pid), is_active=True)
            .first()
        )
    except Exception:
        pu = None
    return pu


def get_portal_user_from_token(request: HttpRequest) -> Optional[PortalUser]:
    auth = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")
    token = _extract_token(auth)
    if not token:
        return None
    return (
        PortalUser.objects.select_related("party", "owner")
        .prefetch_related("permissions")
        .filter(api_token=token, is_active=True)
        .first()
    )


def _portal_perms_map(portal_user: PortalUser) -> dict[str, bool]:
    perms: dict[str, bool] = {}
    try:
        for p in portal_user.permissions.all():
            perms[str(p.key)] = bool(p.allowed)
    except Exception:
        perms = {}
    return perms


def portal_login_required(*, role: str | None = None, permission: str | None = None, api: bool = False) -> Callable:
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            portal_user = get_portal_user_from_session(request)
            if not portal_user:
                if api:
                    return JsonResponse({"ok": False, "error": "Portal login required"}, status=401)
                return redirect("accounts:login")

            # Global portal enable/disable gating (admin settings)
            try:
                from portal.services import customer_portal_enabled, portal_enabled, supplier_portal_enabled

                if not portal_enabled():
                    for k in ("portal_user_id", "portal_role"):
                        try:
                            request.session.pop(k, None)
                        except Exception:
                            pass
                    if api:
                        return JsonResponse({"ok": False, "error": "Portal is disabled"}, status=403)
                    messages.error(request, "Portal is currently disabled.")
                    return redirect("accounts:login")

                if portal_user.role == PortalUser.Role.CUSTOMER and not customer_portal_enabled():
                    for k in ("portal_user_id", "portal_role"):
                        try:
                            request.session.pop(k, None)
                        except Exception:
                            pass
                    if api:
                        return JsonResponse({"ok": False, "error": "Customer portal is disabled"}, status=403)
                    messages.error(request, "Customer portal is currently disabled.")
                    return redirect("accounts:login")

                if portal_user.role == PortalUser.Role.SUPPLIER and not supplier_portal_enabled():
                    for k in ("portal_user_id", "portal_role"):
                        try:
                            request.session.pop(k, None)
                        except Exception:
                            pass
                    if api:
                        return JsonResponse({"ok": False, "error": "Supplier portal is disabled"}, status=403)
                    messages.error(request, "Supplier portal is currently disabled.")
                    return redirect("accounts:login")
            except Exception:
                # Never break portal pages due to settings read errors.
                pass

            if role and portal_user.role != role:
                if api:
                    return JsonResponse({"ok": False, "error": "Invalid portal role"}, status=403)
                return redirect("accounts:login")

            perms = _portal_perms_map(portal_user)
            request.portal_user = portal_user  # type: ignore[attr-defined]
            request.portal_perms = perms  # type: ignore[attr-defined]
            try:
                from portal.services import customer_split_dashboards_enabled, supplier_split_dashboards_enabled

                request.portal_ui = {  # type: ignore[attr-defined]
                    "customer_split_dashboards": bool(customer_split_dashboards_enabled()),
                    "supplier_split_dashboards": bool(supplier_split_dashboards_enabled()),
                }
            except Exception:
                request.portal_ui = {"customer_split_dashboards": True, "supplier_split_dashboards": True}  # type: ignore[attr-defined]

            # Must change password: force redirect (except logout / change password view).
            if not api and getattr(portal_user, "must_change_password", False):
                try:
                    change_url = reverse("portal:change_password")
                    logout_url = reverse("portal:logout")
                except Exception:
                    change_url = "/portal/change-password/"
                    logout_url = "/portal/logout/"
                if request.path not in {change_url, logout_url}:
                    messages.info(request, "Please change your portal password to continue.")
                    return redirect("portal:change_password")

            if permission:
                allowed = perms.get(permission, True)
                if allowed is False:
                    if api:
                        return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)
                    messages.error(request, "Permission denied.")
                    # Prefer sending portal users back to their dashboard.
                    if portal_user.role == PortalUser.Role.SUPPLIER:
                        return redirect("portal:supplier_dashboard")
                    return redirect("portal:customer_dashboard")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
