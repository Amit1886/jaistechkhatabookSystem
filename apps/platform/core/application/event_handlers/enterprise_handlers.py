from apps.platform.core.application.services.rule_engine import RuleEngine
from apps.platform.identity.application.services.audit_service import AuditService
from apps.platform.identity.application.services.notification_service import NotificationService


class EnterpriseEventHandler:
    def __init__(self, rule_engine=None, audit_service=None, notification_service=None):
        self.rule_engine = rule_engine or RuleEngine()
        self.audit_service = audit_service or AuditService()
        self.notification_service = notification_service or NotificationService()

    def handle(self, event_type, payload, tenant=None, user=None):
        actions = self.rule_engine.evaluate("automation", {"event_type": event_type, **(payload or {})}, tenant=tenant)
        self._audit(event_type, payload, tenant, user)
        self._notify(event_type, payload, tenant, user, actions)
        return {"event_type": event_type, "actions": actions}

    def _audit(self, event_type, payload, tenant, user):
        try:
            self.audit_service.log(
                tenant=tenant,
                user=user,
                action=event_type,
                object_type=payload.get("object_type", "event") if isinstance(payload, dict) else "event",
                object_id=str(payload.get("id", "")) if isinstance(payload, dict) else "",
                metadata={"payload": payload},
            )
        except Exception:
            return

    def _notify(self, event_type, payload, tenant, user, actions):
        if not user:
            return
        try:
            self.notification_service.send(
                user=user,
                tenant=tenant,
                title=event_type.replace("_", " ").title(),
                message="Enterprise event processed.",
                severity="info",
                metadata={"payload": payload, "actions": actions},
            )
        except Exception:
            return

