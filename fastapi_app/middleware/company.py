from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware


class CompanyContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.company_id = request.headers.get("x-company-id", "")
        request.state.tenant_id = request.headers.get("x-tenant-id", "")
        return await call_next(request)
