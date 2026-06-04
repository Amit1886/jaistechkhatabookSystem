from apps.platform.identity.infrastructure.repositories.identity_repository import IdentityRepository


class NotificationService:
    def __init__(self, repository=None):
        self.repository = repository or IdentityRepository()

    def send(self, *, user, tenant=None, title, message="", severity="info", action_url="", metadata=None):
        return self.repository.notify(
            tenant=tenant,
            user=user,
            title=title,
            message=message,
            severity=severity,
            action_url=action_url,
            metadata=metadata or {},
        )
