from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin


class TenantBootstrapMiddleware(MiddlewareMixin):
    """
    Lightweight compatibility middleware.

    - In current Billentra codebase, tenancy is "subdomain resolved vendor" (single DB).
    - In future, after enabling django-tenants, request.tenant will be set by TenantMainMiddleware.

    This middleware adds a stable `request.tenant_subdomain` that backend code can use
    without caring which tenancy engine is active.
    """

    def process_request(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            request.tenant_subdomain = getattr(tenant, "subdomain", "") or ""
            return None
        request.tenant_subdomain = getattr(request, "vendor_subdomain", "") or ""
        return None

