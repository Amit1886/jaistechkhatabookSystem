from django.db.models.signals import post_save
from django.dispatch import receiver

from realtime.services.publisher import publish_event
from wallet.models import WalletTransaction, WithdrawRequest


@receiver(post_save, sender=WalletTransaction)
def publish_wallet_txn(sender, instance: WalletTransaction, created: bool, **kwargs):
    if not created:
        return
    payload = {
        "id": instance.id,
        "user": instance.wallet.user_id,
        "entry_type": instance.entry_type,
        "amount": float(instance.amount),
        "source": instance.source,
        "reference": instance.reference,
        "created_at": instance.created_at.isoformat(),
    }
    publish_event("earnings_live", "wallet.transaction", payload)


@receiver(post_save, sender=WithdrawRequest)
def publish_withdraw_status(sender, instance: WithdrawRequest, created: bool, **kwargs):
    payload = {
        "id": instance.id,
        "user": instance.user_id,
        "amount": float(instance.amount),
        "status": instance.status,
        "requested_at": instance.requested_at.isoformat(),
        "processed_at": instance.processed_at.isoformat() if instance.processed_at else None,
    }
    event = "withdraw.created" if created else "withdraw.updated"
    publish_event("earnings_live", event, payload)
