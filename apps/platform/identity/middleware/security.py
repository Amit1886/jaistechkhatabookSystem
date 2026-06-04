from django.http import JsonResponse

from apps.platform.identity.application.services.audit_service import AuditService, client_ip
from apps.platform.identity.application.services.permission_service import PermissionService
from apps.platform.identity.application.services.session_service import SessionService
from apps.platform.identity.application.services.tenant_service import TenantService


class EnterpriseTenantMiddleware:
    """
    Adds request.identity_tenant without replacing existing tenant middleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.service = TenantService()

    def __call__(self, request):
        self.service.attach_request_tenant(request)
        return self.get_response(request)


class EnterpriseSessionActivityMiddleware:
    """
    Tracks active authenticated sessions. Fails open if tables are not migrated.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.session_service = SessionService()

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self.session_service.track_request(request, tenant=getattr(request, "identity_tenant", None))
        except Exception:
            pass
        return response


class EnterprisePermissionMiddleware:
    """
    Strict permission middleware with compatibility defaults.

    Views can set `enterprise_permission_required = "module.action"`.
    URL patterns can also add `request.resolver_match.kwargs["enterprise_permission"]`.
    Undefined enterprise permissions are allowed until configured.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.permission_service = PermissionService()
        self.audit = AuditService()

    def __call__(self, request):
        decision = self._check_request(request)
        if decision is not None and not decision.allowed:
            try:
                self.audit.log(
                    request=request,
                    action="identity.permission_denied",
                    object_type="request",
                    object_id=request.path,
                    metadata={"reason": decision.reason},
                )
            except Exception:
                pass
            if request.path.startswith("/api/"):
                return JsonResponse({"detail": "Permission denied", "reason": decision.reason}, status=403)
        return self.get_response(request)

    def _check_request(self, request):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return None

        time_decision = self.permission_service.within_time_window(user)
        if not time_decision.allowed:
            return time_decision

        permission_key = ""
        match = getattr(request, "resolver_match", None)
        if match:
            permission_key = getattr(getattr(match, "func", None), "enterprise_permission_required", "") or ""
            if not permission_key and hasattr(match, "kwargs"):
                permission_key = match.kwargs.get("enterprise_permission", "")
        if not permission_key:
            return None
        return self.permission_service.has_permission(
            user,
            permission_key,
            tenant=getattr(request, "identity_tenant", None),
        )


class EnterpriseIPDeviceRestrictionMiddleware:
    """
    Optional IP/device restriction using user.permissions_json.

    Supported keys:
    - allowed_ips: list[str]
    - blocked_ips: list[str]
    - require_trusted_device: bool
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.audit = AuditService()

    def __call__(self, request):
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False) and not self._allowed(request, user):
            try:
                self.audit.log(request=request, action="identity.access_restricted", object_type="request", object_id=request.path)
            except Exception:
                pass
            if request.path.startswith("/api/"):
                return JsonResponse({"detail": "Access restricted"}, status=403)
        return self.get_response(request)

    def _allowed(self, request, user):
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        rules = getattr(user, "permissions_json", None) or {}
        ip = client_ip(request)
        blocked = set(rules.get("blocked_ips") or [])
        allowed = set(rules.get("allowed_ips") or [])
        if ip and ip in blocked:
            return False
        if allowed and ip not in allowed:
            return False
        # Device trust enforcement is deliberately configuration-only for now.
        return True
