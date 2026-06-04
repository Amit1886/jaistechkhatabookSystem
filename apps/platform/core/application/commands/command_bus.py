from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.platform.core.application.services.event_service import EventService
from apps.platform.core.application.services.policy_engine import PolicyEngine
from apps.platform.core.domain.commands import Command
from apps.platform.core.models import CommandEnvelope
from apps.platform.identity.models import Tenant


class CommandBus:
    def __init__(self, policy_engine=None, event_service=None):
        self.policy_engine = policy_engine or PolicyEngine()
        self.event_service = event_service or EventService()

    @transaction.atomic
    def dispatch(self, command: Command):
        tenant = Tenant.objects.filter(id=command.tenant_id).first() if command.tenant_id else None
        user = get_user_model().objects.filter(id=command.actor_id).first() if command.actor_id else None
        envelope = CommandEnvelope.objects.create(
            tenant=tenant,
            command_type=command.command_type,
            idempotency_key=command.idempotency_key,
            payload=command.payload,
            status=CommandEnvelope.Status.ACCEPTED,
            requested_by=user,
        )
        decision = self.policy_engine.evaluate("approval", command.payload, tenant=tenant)
        if not decision.allowed:
            envelope.status = CommandEnvelope.Status.FAILED
            envelope.error = decision.reason
            envelope.result = decision.effects
            envelope.save(update_fields=["status", "error", "result", "updated_at"])
            return envelope
        self.event_service.publish(
            f"{command.command_type}_accepted",
            {"command_id": str(envelope.id), **command.payload},
            tenant=tenant,
            user=user,
            topic=getattr(settings, "ERP_EVENT_TOPIC", "erp.core"),
            key=str(envelope.id),
        )
        envelope.status = CommandEnvelope.Status.COMPLETED
        envelope.result = {"accepted": True, "correlation_id": command.correlation_id}
        envelope.save(update_fields=["status", "result", "updated_at"])
        return envelope

