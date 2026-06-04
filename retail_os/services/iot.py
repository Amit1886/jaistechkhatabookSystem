from django.utils import timezone

from ..models import DeviceEvent, DeviceHealth, DeviceLog, IoTDevice
from .realtime import publish_retail_event


def register_device_event(device, event_type, payload, branch=None, product=None):
    event = DeviceEvent.objects.create(device=device, event_type=event_type, branch=branch or device.branch, product=product, payload=payload)
    IoTDevice.objects.filter(pk=device.pk).update(is_online=True, last_seen_at=timezone.now())
    publish_retail_event(
        "iot",
        f"device.{event_type}",
        {"device_id": device.id, "device_uid": device.device_uid, "branch_id": event.branch_id, "payload": payload},
    )
    return event


def record_device_health(device, status="online", metrics=None, battery_percent=None, signal_strength=None, error_message=""):
    health, _ = DeviceHealth.objects.get_or_create(device=device)
    health.status = status
    health.metrics = metrics or {}
    health.battery_percent = battery_percent
    health.signal_strength = signal_strength
    if error_message:
        health.error_count += 1
        health.last_error = error_message
        DeviceLog.objects.create(device=device, level="error", message=error_message, payload=metrics or {})
    health.save()
    IoTDevice.objects.filter(pk=device.pk).update(is_online=status == "online", last_seen_at=timezone.now())
    publish_retail_event("iot", "device.health", {"device_id": device.id, "status": status, "metrics": metrics or {}})
    return health

