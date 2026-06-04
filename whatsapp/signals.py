from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from whatsapp.models import Bot, WhatsAppAccount


@receiver(post_save, sender=WhatsAppAccount)
def ensure_default_bot(sender, instance: WhatsAppAccount, created: bool, **kwargs):
    if not created:
        return
    Bot.objects.get_or_create(
        whatsapp_account=instance,
        defaults={
            "owner": instance.owner,
            "name": instance.label or "WhatsApp Bot",
            "kind": Bot.Kind.ORDER,
            "is_enabled": True,
            "auto_reply_enabled": True,
            "ai_fallback_enabled": True,
        },
    )

