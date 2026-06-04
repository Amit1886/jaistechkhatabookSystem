from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from khataapp.models import Party
from portal.services import create_portal_account_for_party

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Party, dispatch_uid="portal_autocreate_party_portal_account_v1")
def autocreate_portal_account(sender, instance: Party, created: bool, **kwargs):
    """
    Auto-create portal login whenever a new customer/supplier is created.
    """
    if not created:
        return
    try:
        create_portal_account_for_party(instance, created_by=getattr(instance, "owner", None))
    except Exception:
        logger.exception("Portal auto account creation failed for party id=%s", getattr(instance, "id", None))

