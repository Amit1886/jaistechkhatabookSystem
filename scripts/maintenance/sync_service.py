from __future__ import annotations

import logging
import os
import socket
import threading
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests


logger = logging.getLogger(__name__)


DEFAULT_SYNC_INTERVAL_SECONDS = 30
DEFAULT_OBJECT_SYNC_PATH = "/api/v1/sync/push/"
LEGACY_INVOICE_SYNC_PATH = "/api/v1/sync/invoices/"


def _cloud_api_url() -> str:
    return (os.getenv("CLOUD_API_URL") or "").strip().rstrip("/")


def _cloud_api_token() -> str:
    # Token used by the desktop app to authenticate against the cloud API.
    return (os.getenv("CLOUD_API_TOKEN") or "").strip()


def _cloud_invoice_sync_url() -> str:
    base = _cloud_api_url()
    if not base:
        return ""
    return urljoin(base + "/", LEGACY_INVOICE_SYNC_PATH.lstrip("/"))


def _cloud_object_sync_url() -> str:
    base = _cloud_api_url()
    if not base:
        return ""
    return urljoin(base + "/", DEFAULT_OBJECT_SYNC_PATH.lstrip("/"))


def _auth_headers() -> dict[str, str]:
    token = _cloud_api_token()
    if not token:
        return {}
    return {"Authorization": f"Token {token}"}


def _cloud_host_reachable(url: str, *, timeout_seconds: float = 2.0) -> bool:
    """
    Best-effort reachability check for the configured cloud host.

    Avoids hard-coding 8.8.8.8:53 (which can be blocked on many networks) and
    instead checks that the target cloud host:port is connectable.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return False
        port = int(parsed.port or (443 if (parsed.scheme or "").lower() == "https" else 80))
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _ensure_payload(item) -> dict[str, Any]:
    """
    Ensure a SyncQueue row has a useful payload.

    Newer desktop builds write payload at save-time via `commerce.desktop_sync`.
    For older rows (or legacy DBs), try to fetch the object and serialize it.
    """
    payload = item.payload if isinstance(getattr(item, "payload", None), dict) else {}
    if payload:
        return payload

    # Don't force payload for deletes (object might be gone).
    if str(getattr(item, "action", "")).lower() == "delete":
        return {}

    try:
        from django.apps import apps  # noqa: WPS433
        from commerce.desktop_sync import serialize_instance  # noqa: WPS433

        model = apps.get_model(item.model_name)
        obj = model.objects.filter(pk=item.object_id).first()
        if not obj:
            return {}
        payload = serialize_instance(obj) or {}
        if isinstance(payload, dict):
            try:
                type(item).objects.filter(pk=item.pk, synced=False).update(payload=payload)
            except Exception:
                pass
            return payload
    except Exception:
        return {}

    return {}


class SyncService(threading.Thread):
    """
    Background sync worker:
    - every N seconds: if cloud is reachable, push unsynced SyncQueue rows to cloud API
    """

    daemon = True

    def __init__(self, interval_seconds: int = DEFAULT_SYNC_INTERVAL_SECONDS):
        super().__init__(name="sync-service")
        self.interval_seconds = int(interval_seconds)
        self._stop_event = threading.Event()
        self._last_unreachable_log = 0.0

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        from django.db import close_old_connections  # noqa: WPS433

        while not self._stop_event.is_set():
            try:
                close_old_connections()
                self.sync_once()
            except Exception:
                logger.exception("SyncService loop error")
            self._stop_event.wait(self.interval_seconds)

    def sync_once(self) -> None:
        sync_url = _cloud_object_sync_url()
        if not sync_url:
            # No cloud configured; stay in offline-only mode.
            return

        # Lazy imports (Django app registry must be ready).
        from commerce.models import SyncQueue  # noqa: WPS433
        from django.utils import timezone  # noqa: WPS433

        try:
            from commerce.desktop_sync import get_desktop_device_id  # noqa: WPS433
        except Exception:
            get_desktop_device_id = lambda: ""  # type: ignore[assignment]

        batch = (
            SyncQueue.objects.filter(synced=False)
            .order_by("created_at", "id")[:50]
        )
        if not batch:
            return

        if not _cloud_host_reachable(sync_url):
            # Throttle noise if network is down/captive portal/etc.
            now = time.time()
            if (now - self._last_unreachable_log) > 60:
                self._last_unreachable_log = now
                logger.info("Cloud is not reachable yet; will retry. Cloud=%s", _cloud_api_url() or "<unset>")
            return

        device_id = ""
        try:
            device_id = str(get_desktop_device_id() or "").strip()
        except Exception:
            device_id = ""

        rows: list[dict[str, Any]] = []
        sent_items = []
        items = list(batch)
        for item in items:
            if self._stop_event.is_set():
                return

            action = str(item.action or "").strip().lower()
            if action not in {"create", "update", "delete"}:
                # Poison pill: mark as synced so it doesn't block the queue.
                SyncQueue.objects.filter(pk=item.pk, synced=False).update(
                    synced=True,
                    attempts=item.attempts + 1,
                    last_error=f"Invalid action: {action!r}",
                    last_attempt_at=timezone.now(),
                )
                continue

            did = str(item.device_id or device_id or "").strip()
            if did and not item.device_id:
                try:
                    SyncQueue.objects.filter(pk=item.pk, synced=False).update(device_id=did)
                except Exception:
                    pass

            payload = _ensure_payload(item)
            rows.append(
                {
                    "device_id": did,
                    "model": str(item.model_name or ""),
                    "local_id": str(item.object_id or ""),
                    "action": action,
                    "payload": payload or {},
                }
            )
            sent_items.append(item)

        if not rows:
            return

        started_at = timezone.now()

        try:
            resp = requests.post(
                sync_url,
                json=rows,
                headers={
                    "Content-Type": "application/json",
                    **_auth_headers(),
                },
                timeout=20,
            )
        except requests.RequestException as e:
            err = f"Request failed: {e}"
            logger.warning("Cloud sync request failed: %s", err)
            for item in sent_items:
                SyncQueue.objects.filter(pk=item.pk, synced=False).update(
                    attempts=item.attempts + 1,
                    last_error=err,
                    last_attempt_at=started_at,
                )
            return

        if not (200 <= resp.status_code < 300):
            err = f"HTTP {resp.status_code}: {(resp.text or '')[:500]}"
            logger.warning("Cloud sync rejected: %s", err)
            for item in sent_items:
                SyncQueue.objects.filter(pk=item.pk, synced=False).update(
                    attempts=item.attempts + 1,
                    last_error=err,
                    last_attempt_at=started_at,
                )
            return

        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}

        results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(results, list) or len(results) != len(rows):
            err = "Unexpected sync response format"
            logger.warning("%s: %s", err, (resp.text or "")[:500])
            for item in sent_items:
                SyncQueue.objects.filter(pk=item.pk, synced=False).update(
                    attempts=item.attempts + 1,
                    last_error=err,
                    last_attempt_at=started_at,
                )
            return

        for item, res in zip(sent_items, results):
            ok = bool(res.get("ok")) if isinstance(res, dict) else False
            status_txt = str(res.get("status") or "") if isinstance(res, dict) else ""
            msg = str(res.get("message") or res.get("error") or "") if isinstance(res, dict) else ""

            if ok and status_txt in {"stored", "applied"}:
                SyncQueue.objects.filter(pk=item.pk, synced=False).update(
                    synced=True,
                    attempts=item.attempts + 1,
                    last_error="",
                    last_attempt_at=started_at,
                )
            else:
                # Keep queued for retry (e.g., pending_dependency).
                SyncQueue.objects.filter(pk=item.pk, synced=False).update(
                    attempts=item.attempts + 1,
                    last_error=(f"{status_txt}: {msg}".strip(": ").strip() if (status_txt or msg) else "sync_failed"),
                    last_attempt_at=started_at,
                )


def start_sync_service(interval_seconds: int = DEFAULT_SYNC_INTERVAL_SECONDS) -> SyncService:
    """
    Start the background sync service (call after `django.setup()`).
    """
    svc = SyncService(interval_seconds=interval_seconds)
    svc.start()
    logger.info("SyncService started (interval=%ss, cloud=%s)", int(interval_seconds), _cloud_api_url() or "<unset>")
    return svc
