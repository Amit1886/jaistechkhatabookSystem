from __future__ import annotations

from typing import Any

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.db import OperationalError, transaction

from realtime.services.publisher import publish_event

from .models import SystemMode


CACHE_KEY = "system_mode_state_v1"
CACHE_TTL_SECONDS = 5


def serialize_system_mode(mode_obj: SystemMode) -> dict[str, Any]:
    return {
        "current_mode": str(mode_obj.current_mode),
        "is_locked": bool(mode_obj.is_locked),
        "updated_by_id": mode_obj.updated_by_id,
        "updated_at": mode_obj.updated_at.isoformat() if mode_obj.updated_at else None,
    }


def get_system_mode_state(force_refresh: bool = False) -> dict[str, Any]:
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached

    try:
        mode_obj = SystemMode.get_solo()
        payload = serialize_system_mode(mode_obj)
    except OperationalError:
        payload = {
            "current_mode": SystemMode.Mode.DESKTOP.value,
            "is_locked": False,
            "updated_by_id": None,
            "updated_at": None,
        }

    cache.set(CACHE_KEY, payload, CACHE_TTL_SECONDS)
    return payload


def _resolve_auto_mode(request) -> str:
    width_header = request.headers.get("X-Viewport-Width") or request.META.get("HTTP_X_VIEWPORT_WIDTH")
    if width_header:
        try:
            width = int(width_header)
            if width <= 767:
                return SystemMode.Mode.MOBILE
            if width <= 1199:
                return SystemMode.Mode.TABLET
            return SystemMode.Mode.DESKTOP
        except ValueError:
            pass

    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    if "ipad" in ua or "tablet" in ua:
        return SystemMode.Mode.TABLET
    if "mobile" in ua:
        return SystemMode.Mode.MOBILE
    if "android" in ua and "mobile" not in ua:
        return SystemMode.Mode.TABLET
    return SystemMode.Mode.DESKTOP


def resolve_mode_for_request(request, state: dict[str, Any] | None = None) -> str:
    state = state or get_system_mode_state()
    requested = str(state.get("current_mode", SystemMode.Mode.DESKTOP.value))

    if requested == SystemMode.Mode.AUTO:
        return _resolve_auto_mode(request)

    if requested == SystemMode.Mode.ADMIN_SUPER and not getattr(request.user, "is_staff", False):
        return SystemMode.Mode.DESKTOP

    return str(requested)


def route_profile_for_mode(resolved_mode: str) -> dict[str, str]:
    route_map = {
        SystemMode.Mode.POS: {
            "entry_route": "/pos/ui/",
            "layout_key": "pos_embedded",
            "navigation_style": "minimal",
        },
        SystemMode.Mode.MOBILE: {
            "entry_route": "/app/",
            "layout_key": "mobile",
            "navigation_style": "bottom_tabs",
        },
        SystemMode.Mode.TABLET: {
            "entry_route": "/commerce/dashboard/",
            "layout_key": "tablet",
            "navigation_style": "split",
        },
        SystemMode.Mode.DESKTOP: {
            "entry_route": "/accounts/dashboard/",
            "layout_key": "desktop",
            "navigation_style": "full_sidebar",
        },
        SystemMode.Mode.ADMIN_SUPER: {
            "entry_route": "/superadmin/",
            "layout_key": "admin_super",
            "navigation_style": "control_tower",
        },
    }
    return route_map.get(resolved_mode, route_map[SystemMode.Mode.DESKTOP])


def build_request_mode_context(request) -> dict[str, Any]:
    state = get_system_mode_state()
    resolved_mode = resolve_mode_for_request(request, state)
    route_profile = route_profile_for_mode(resolved_mode)

    return {
        **state,
        "resolved_mode": resolved_mode,
        "resolved_mode_css": resolved_mode.lower(),
        "route_profile": route_profile,
    }


def _broadcast_mode_changed(payload: dict[str, Any]) -> None:
    event = {
        "event_type": "system.mode.changed",
        "payload": payload,
        "force_reload": True,
        "apply_layout_immediately": True,
    }

    # Persist + broadcast to existing realtime stream system.
    try:
        publish_event("system_mode", "system.mode.changed", event)
    except Exception:
        pass

    # Dedicated group for explicit system-mode websocket clients.
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            "system_mode",
            {
                "type": "mode_changed",
                "event": event,
            },
        )
    except Exception:
        pass


def switch_system_mode(*, current_mode: str | None, is_locked: bool | None, updated_by) -> dict[str, Any]:
    with transaction.atomic():
        mode_obj = SystemMode.get_solo(for_update=True)

        if current_mode is not None:
            mode_obj.current_mode = current_mode
        if is_locked is not None:
            mode_obj.is_locked = bool(is_locked)
        if getattr(updated_by, "is_authenticated", False):
            mode_obj.updated_by = updated_by
        else:
            mode_obj.updated_by = None

        mode_obj.save()
        payload = serialize_system_mode(mode_obj)
        cache.delete(CACHE_KEY)
        transaction.on_commit(lambda: _broadcast_mode_changed(payload))

    return payload
