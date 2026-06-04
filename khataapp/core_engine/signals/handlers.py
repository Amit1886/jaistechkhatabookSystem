from __future__ import annotations

from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from commerce.models import Invoice, Payment
from khataapp.models import Party, Transaction
from portal.models import PaymentLink

from khataapp.core_engine.services.daily_tasks import complete_task, record_daily_login
from khataapp.core_engine.services.loyalty_service import award_for_transaction, ensure_loyalty_account
from khataapp.core_engine.services.payment_service import record_payment_received
from khataapp.core_engine.services.payment_service import record_payment_link_paid
from khataapp.core_engine.services.reward_service import award_invoice_rewards, award_payment_rewards


@receiver(post_save, sender=Transaction)
def engine_on_transaction_created(sender, instance: Transaction, created: bool, **kwargs):
    if not created:
        return
    if getattr(instance, "is_deleted", False):
        return
    party = getattr(instance, "party", None)
    owner = getattr(party, "owner", None)
    if not owner:
        return

    award_for_transaction(transaction=instance, actor=owner)
    complete_task(owner=owner, task_key="add_transaction", day=getattr(instance, "date", None) or timezone.localdate())


@receiver(post_save, sender=Party)
def engine_on_party_created(sender, instance: Party, created: bool, **kwargs):
    if not created:
        return
    owner = getattr(instance, "owner", None)
    if not owner:
        return

    ensure_loyalty_account(owner=owner, party=instance)
    complete_task(owner=owner, task_key="add_party", day=timezone.localdate())


@receiver(post_save, sender=Invoice)
def engine_on_invoice_created(sender, instance: Invoice, created: bool, **kwargs):
    if not created:
        return
    award_invoice_rewards(invoice=instance)

    owner = getattr(getattr(instance, "order", None), "owner", None)
    if owner:
        complete_task(owner=owner, task_key="create_invoice", day=timezone.localdate(), meta={"invoice_id": instance.id})


@receiver(post_save, sender=Payment)
def engine_on_payment_received(sender, instance: Payment, created: bool, **kwargs):
    if not created:
        return
    record_payment_received(payment=instance)
    award_payment_rewards(payment=instance)


@receiver(post_save, sender=PaymentLink)
def engine_on_payment_link_saved(sender, instance: PaymentLink, created: bool, **kwargs):
    # Status transitions can happen after creation; rely on idempotency guard.
    if (getattr(instance, "status", "") or "").lower() != PaymentLink.Status.PAID:
        return
    record_payment_link_paid(payment_link=instance)


@receiver(user_logged_in)
def engine_on_user_login(sender, request, user, **kwargs):
    record_daily_login(owner=user, actor=user)
