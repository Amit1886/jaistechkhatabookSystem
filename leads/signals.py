from django.db.models.signals import post_save
from django.dispatch import receiver

from leads.models import Lead
from realtime.services.publisher import publish_event
from voice.services import start_voice_call
from voice.models import VoiceCall


@receiver(post_save, sender=Lead)
def publish_lead_events(sender, instance: Lead, created: bool, **kwargs):
    payload = {
        "id": instance.id,
        "name": instance.name,
        "mobile": instance.mobile,
        "email": instance.email,
        "status": instance.status,
        "score": instance.score,
        "assigned_to": instance.assigned_to_id,
        "source": instance.source,
        "created_at": instance.created_at.isoformat(),
    }
    event_type = "lead.created" if created else "lead.updated"
    publish_event("leads_live", event_type, payload)

    # Trigger AI voice call on new leads (best-effort, non-blocking)
    try:
        if created:
            start_voice_call(instance, trigger=VoiceCall.Trigger.NEW_LEAD)
    except Exception:
        # Do not break lead save flow
        pass
