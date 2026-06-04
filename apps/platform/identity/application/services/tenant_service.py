from apps.platform.identity.infrastructure.repositories.identity_repository import IdentityRepository


class TenantService:
    def __init__(self, repository=None):
        self.repository = repository or IdentityRepository()

    def resolve_request_tenant(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant:
            return tenant
        user = getattr(request, "user", None)
        return self.repository.resolve_tenant_for_user(user)

    def attach_request_tenant(self, request):
        tenant = self.resolve_request_tenant(request)
        request.identity_tenant = tenant
        return tenant
