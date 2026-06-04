from django.utils import timezone

from realtime.models import RealtimeEvent


def publish_retail_event(stream_name: str, event_type: str, payload: dict) -> None:
    event = RealtimeEvent.objects.create(channel=stream_name, event_type=event_type, payload=payload)
    message = {
        "type": "broadcast",
        "payload": {
            "event_id": event.id,
            "event_type": event_type,
            "payload": payload,
            "created_at": timezone.now().isoformat(),
        },
    }
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except Exception:
        return
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(f"stream_{stream_name}", message)
