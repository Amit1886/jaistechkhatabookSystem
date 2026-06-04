from django.utils import timezone

from apps.platform.core.infrastructure.repositories.core_repository import CoreRepository, DB_NOT_READY


class EventService:
    def __init__(self, repository=None):
        self.repository = repository or CoreRepository()

    def publish(self, event_type, payload, tenant=None, user=None, topic="erp.core", key=""):
        event_id = None
        try:
            from event_bus.models import EventOutbox

            event = EventOutbox.objects.create(
                owner=user if getattr(user, "is_authenticated", False) else None,
                topic=topic,
                event_type=event_type,
                key=key or str(payload.get("id") or payload.get("reference_no") or ""),
                payload={"tenant_id": str(tenant.id) if tenant else None, "data": payload},
            )
            event_id = str(event.id)
        except Exception:
            event_id = None

        self.dispatch_local(event_type=event_type, payload=payload, tenant=tenant, user=user)
        return {"event_id": event_id, "event_type": event_type, "published_at": timezone.now().isoformat()}

    def dispatch_local(self, event_type, payload, tenant=None, user=None):
        try:
            subscriptions = list(self.repository.event_subscriptions(event_type, tenant))
            rules = list(self.repository.automation_rules(event_type, tenant))
        except DB_NOT_READY:
            return
        try:
            from apps.platform.core.application.event_handlers.enterprise_handlers import EnterpriseEventHandler

            EnterpriseEventHandler().handle(event_type, payload, tenant=tenant, user=user)
        except Exception:
            pass
        for subscription in subscriptions:
            self._handle_subscription(subscription, event_type, payload, tenant, user)
        for rule in rules:
            self._run_automation(rule, event_type, payload, tenant)

    def _handle_subscription(self, subscription, event_type, payload, tenant, user):
        handler_type = subscription.handler_type
        if handler_type == "notification":
            try:
                from apps.platform.identity.application.services.notification_service import NotificationService

                NotificationService().send(
                    user=user,
                    tenant=tenant,
                    title=subscription.handler_config.get("title", event_type.replace("_", " ").title()),
                    message=subscription.handler_config.get("message", "ERP event triggered."),
                    severity=subscription.handler_config.get("severity", "info"),
                    metadata={"event_type": event_type, "payload": payload},
                )
            except Exception:
                return

    def _run_automation(self, rule, event_type, payload, tenant):
        status = "success"
        result = {"actions": []}
        error = ""
        try:
            for action in rule.actions or []:
                result["actions"].append({"type": action.get("type"), "status": "queued"})
        except Exception as exc:
            status = "failed"
            error = str(exc)
        self.repository.create_automation_run(
            tenant=tenant,
            rule=rule,
            event_type=event_type,
            payload=payload,
            status=status,
            result=result,
            error=error,
        )
