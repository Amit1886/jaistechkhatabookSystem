from apps.platform.identity.infrastructure.repositories.identity_repository import IdentityRepository


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditService:
    def __init__(self, repository=None):
        self.repository = repository or IdentityRepository()

    def log(self, *, request=None, tenant=None, user=None, action="", object_type="", object_id="", before=None, after=None, metadata=None):
        if request is not None:
            user = user or getattr(request, "user", None)
            tenant = tenant or getattr(request, "identity_tenant", None)
            ip = client_ip(request)
            user_agent = request.META.get("HTTP_USER_AGENT", "")
        else:
            ip = None
            user_agent = ""
        if not getattr(user, "is_authenticated", False):
            user = None
        return self.repository.create_audit_log(
            tenant=tenant,
            user=user,
            action=action,
            actor_ip=ip,
            user_agent=user_agent[:2000],
            object_type=object_type,
            object_id=str(object_id or ""),
            before=before or {},
            after=after or {},
            metadata=metadata or {},
        )
