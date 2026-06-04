from apps.platform.identity.application.services.audit_service import client_ip
from apps.platform.identity.infrastructure.repositories.identity_repository import IdentityRepository


class SessionService:
    DEVICE_HEADER = "HTTP_X_DEVICE_FINGERPRINT"

    def __init__(self, repository=None):
        self.repository = repository or IdentityRepository()

    def track_request(self, request, *, tenant=None):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return None
        session_key = getattr(getattr(request, "session", None), "session_key", None)
        if not session_key:
            try:
                request.session.save()
                session_key = request.session.session_key
            except Exception:
                session_key = ""
        ip = client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        fingerprint = request.META.get(self.DEVICE_HEADER) or request.COOKIES.get("device_fingerprint", "")
        device = self.repository.get_or_create_device(
            tenant=tenant,
            user=user,
            fingerprint=fingerprint,
            ip_address=ip,
            user_agent=user_agent,
        )
        return self.repository.upsert_activity_session(
            tenant=tenant,
            user=user,
            session_key=session_key,
            ip_address=ip,
            user_agent=user_agent,
            device=device,
        )
