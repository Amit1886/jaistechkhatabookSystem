from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def publish_cart(session, cart):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"selfcheckout_{session.session_key}",
        {"type": "cart.update", "cart": cart},
    )


def publish_payment(session, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"selfcheckout_{session.session_key}",
        {"type": "payment.update", "payload": payload},
    )


def publish_kiosk_event(session, event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"selfcheckout_{session.session_key}",
        {"type": "kiosk.event", "event_type": event_type, "payload": payload},
    )


def publish_store_event(owner_id, event_type, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"selfcheckout_store_{owner_id}",
        {"type": "store.event", "event_type": event_type, "payload": payload},
    )
