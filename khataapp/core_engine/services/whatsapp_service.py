from __future__ import annotations

from typing import Optional

from django.db import transaction

from khataapp.core_engine.models.logs import EngineEventLog
from khataapp.core_engine.services.admin_control import get_engine_flags
from khataapp.core_engine.services.plan_access import can_access_feature
from khataapp.core_engine.utils.engine import get_or_create_engine_for_update


@transaction.atomic
def consume_whatsapp_credit(*, owner, credits: int = 1) -> bool:
    if not owner or not getattr(owner, "is_authenticated", False):
        return False
    if not can_access_feature(owner, "engine.notifications").allowed:
        return False

    flags = get_engine_flags()
    if not flags.enable_notifications:
        return False

    engine = get_or_create_engine_for_update(owner)
    needed = max(0, int(credits or 0))
    if needed <= 0:
        return True
    if int(engine.whatsapp_credits) < needed:
        return False

    engine.whatsapp_credits = int(engine.whatsapp_credits) - needed
    engine.save(update_fields=["whatsapp_credits", "updated_at"])
    return True


@transaction.atomic
def queue_message(
    *,
    owner,
    message: str,
    channel: str = "whatsapp",
    party=None,
    recipient_name: str = "",
    recipient_mobile: str = "",
    actor=None,
    meta: Optional[dict] = None,
) -> bool:
    """
    Store message in existing OfflineMessage queue (backward compatible).
    """
    if not owner or not getattr(owner, "is_authenticated", False):
        return False
    if not can_access_feature(owner, "engine.notifications").allowed:
        return False

    flags = get_engine_flags()
    if not flags.enable_notifications:
        return False

    # Decrement credits only for WhatsApp channel.
    if (channel or "").lower() == "whatsapp":
        if not consume_whatsapp_credit(owner=owner, credits=1):
            EngineEventLog.objects.create(
                owner=owner,
                actor=actor,
                category=EngineEventLog.Category.FLOW,
                level=EngineEventLog.Level.WARN,
                event_key="notify.insufficient_credits",
                message="Insufficient WhatsApp credits; message not queued.",
                meta={"channel": channel, "recipient_mobile": recipient_mobile, **(meta or {})},
            )
            return False

    try:
        from khataapp.models import OfflineMessage

        OfflineMessage.objects.create(
            party=party,
            recipient_name=recipient_name or (getattr(party, "name", "") if party else ""),
            recipient_mobile=recipient_mobile or (getattr(party, "whatsapp_number", "") if party else ""),
            message=message,
            channel=channel,
            status="pending",
        )
    except Exception:
        return False

    EngineEventLog.objects.create(
        owner=owner,
        actor=actor,
        category=EngineEventLog.Category.FLOW,
        level=EngineEventLog.Level.INFO,
        event_key="notify.queued",
        message="Notification queued.",
        meta={"channel": channel, "recipient_mobile": recipient_mobile, **(meta or {})},
    )
    return True

