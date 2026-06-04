from django.db.models.signals import post_save
from django.dispatch import receiver

from marketing.models import Campaign, CampaignMessage
from realtime.services.publisher import publish_event


@receiver(post_save, sender=Campaign)
def publish_campaign(sender, instance: Campaign, created: bool, **kwargs):
    payload = {
        "id": instance.id,
        "name": instance.name,
        "channel": instance.channel,
        "status": instance.status,
        "scheduled_at": instance.scheduled_at.isoformat() if instance.scheduled_at else None,
        "started_at": instance.started_at.isoformat() if instance.started_at else None,
        "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
        "recipients_total": instance.recipients_total,
        "recipients_sent": instance.recipients_sent,
        "recipients_failed": instance.recipients_failed,
    }
    event = "campaign.created" if created else "campaign.updated"
    publish_event("marketing_live", event, payload)


@receiver(post_save, sender=CampaignMessage)
def publish_campaign_message(sender, instance: CampaignMessage, created: bool, **kwargs):
    if not created and instance.status not in [CampaignMessage.Status.SENT, CampaignMessage.Status.FAILED]:
        return
    payload = {
        "id": instance.id,
        "campaign_id": instance.campaign_id,
        "lead_id": instance.lead_id,
        "user_id": instance.user_id,
        "destination": instance.destination,
        "status": instance.status,
        "sent_at": instance.sent_at.isoformat() if instance.sent_at else None,
        "provider_ref": instance.provider_ref,
        "last_error": instance.last_error,
    }
    event = "campaign.message.sent" if instance.status == CampaignMessage.Status.SENT else "campaign.message.failed" if instance.status == CampaignMessage.Status.FAILED else "campaign.message.created"
    publish_event("marketing_live", event, payload)
