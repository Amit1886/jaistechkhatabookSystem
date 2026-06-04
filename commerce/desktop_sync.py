from __future__ import annotations

import logging
import os
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.db.utils import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)


_REGISTERED = False
_CACHED_DEVICE_ID: str | None = None


def get_desktop_device_id() -> str:
    """
    Stable desktop device id for sync mapping.

    Stored under `settings.DESKTOP_DATA_DIR/device_id.txt` when possible.
    Can be overridden via `DESKTOP_DEVICE_ID`.
    """
    global _CACHED_DEVICE_ID  # noqa: PLW0603
    if _CACHED_DEVICE_ID is not None:
        return _CACHED_DEVICE_ID

    forced = (os.getenv("DESKTOP_DEVICE_ID") or "").strip()
    if forced:
        _CACHED_DEVICE_ID = forced
        return forced

    try:
        base_dir = Path(str(getattr(settings, "DESKTOP_DATA_DIR", ""))).resolve()
    except Exception:
        base_dir = Path(os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.getcwd())

    device_file = base_dir / "device_id.txt"
    try:
        if device_file.exists():
            existing = device_file.read_text(encoding="utf-8").strip()
            if existing:
                _CACHED_DEVICE_ID = existing
                return existing
    except Exception:
        # Ignore read errors; fallback to generating a new id.
        pass

    new_id = uuid.uuid4().hex
    try:
        device_file.parent.mkdir(parents=True, exist_ok=True)
        device_file.write_text(new_id, encoding="utf-8")
    except Exception:
        # If we cannot persist it, keep it in-memory for this run.
        pass

    _CACHED_DEVICE_ID = new_id
    return new_id


def _jsonify(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}

    try:
        from django.db.models.fields.files import FieldFile  # noqa: WPS433

        if isinstance(value, FieldFile):
            return value.name or ""
    except Exception:
        pass

    # Fallback: ensure JSON-serializable.
    try:
        return str(value)
    except Exception:
        return repr(value)


def serialize_instance(instance: Any) -> dict[str, Any]:
    """
    Serialize a Django model instance into a JSON-friendly payload.

    Format:
      {
        "fields": { ...primitive values... },
        "relations": { "fk_field": {"model": "app.Model", "local_id": "<pk>"} | null },
      }
    """
    fields: dict[str, Any] = {}
    relations: dict[str, Any] = {}

    model_label = getattr(getattr(instance, "_meta", None), "label", "") or ""

    for field in getattr(instance._meta, "concrete_fields", []):
        # Handle FK/OneToOne as relation references.
        if getattr(field, "is_relation", False) and getattr(field, "remote_field", None) is not None:
            if getattr(field, "many_to_one", False) or getattr(field, "one_to_one", False):
                try:
                    remote = field.remote_field.model
                    remote_label = remote._meta.label if remote is not None else ""
                except Exception:
                    remote_label = ""
                try:
                    rel_id = getattr(instance, field.attname, None)
                except Exception:
                    rel_id = None
                if rel_id is None:
                    relations[field.name] = None
                else:
                    relations[field.name] = {"model": str(remote_label), "local_id": str(rel_id)}
            continue

        try:
            raw_value = field.value_from_object(instance)
        except Exception:
            try:
                raw_value = getattr(instance, field.name)
            except Exception:
                raw_value = None
        fields[field.name] = _jsonify(raw_value)

    # Helpful hints for common owner relationships (avoids dependency ordering issues).
    if model_label != "accounts.User":
        try:
            owner = getattr(instance, "owner", None)
            owner_email = getattr(owner, "email", None) if owner is not None else None
            if owner_email:
                fields.setdefault("owner_email", str(owner_email))
        except Exception:
            pass

    # Security/sanity: never sync raw/sensitive fields.
    if model_label == "accounts.User":
        for k in ("password", "last_login"):
            fields.pop(k, None)

    return {"fields": fields, "relations": relations}


def _should_sync_model(sender: Any) -> bool:
    try:
        label = sender._meta.label  # type: ignore[attr-defined]
        app_label = sender._meta.app_label  # type: ignore[attr-defined]
    except Exception:
        return False

    if not label or not app_label:
        return False

    # Avoid recursion / internal inbox rows.
    if label in {
        "commerce.SyncQueue",
        "commerce.SyncedObject",
        "commerce.SyncMapping",
        "commerce.SyncedInvoice",
    }:
        return False

    # Avoid syncing Django/system tables and third-party plumbing.
    if app_label in {
        "admin",
        "auth",
        "contenttypes",
        "sessions",
        "sites",
        "authtoken",
        "rest_framework",
        "rest_framework_simplejwt",
        "drf_spectacular",
        "jazzmin",
        "solo",
    }:
        return False

    # Avoid pushing OTPs/tokens.
    if label in {
        "accounts.OTP",
        "khataapp.LoginLink",
    }:
        return False

    return True


def _enqueue_event(*, model_name: str, local_id: str, action: str, payload: dict[str, Any], using: str | None = None) -> None:
    try:
        from commerce.models import SyncQueue  # noqa: WPS433

        device_id = get_desktop_device_id()
        db = using or "default"
        SyncQueue.objects.using(db).create(
            device_id=device_id,
            model_name=model_name,
            object_id=str(local_id),
            action=action,
            payload=payload or {},
            synced=False,
        )
    except (OperationalError, ProgrammingError):
        # During first-run startup/migrations the queue table may not exist yet.
        # Skip enqueueing instead of blocking the server boot sequence.
        return


def _on_model_saved(sender, instance, created: bool = False, raw: bool = False, using: str | None = None, **kwargs) -> None:
    if raw:
        return
    if not getattr(settings, "DESKTOP_MODE", False):
        return
    if not _should_sync_model(sender):
        return
    try:
        if getattr(instance, "pk", None) is None:
            return
    except Exception:
        return

    model_label = instance._meta.label
    # Skip staff/superuser accounts on desktop; cloud will manage admin users.
    if model_label == "accounts.User":
        try:
            if bool(getattr(instance, "is_staff", False) or getattr(instance, "is_superuser", False)):
                return
        except Exception:
            pass

    from commerce.models import SyncQueue  # noqa: WPS433

    action = SyncQueue.Action.CREATE if created else SyncQueue.Action.UPDATE
    payload = serialize_instance(instance)

    def _enqueue() -> None:
        try:
            _enqueue_event(model_name=model_label, local_id=str(instance.pk), action=action, payload=payload, using=using)
        except Exception:
            logger.exception("Failed to enqueue sync event: %s#%s", model_label, getattr(instance, "pk", "?"))

    transaction.on_commit(_enqueue)


def _on_model_deleted(sender, instance, using: str | None = None, **kwargs) -> None:
    if not getattr(settings, "DESKTOP_MODE", False):
        return
    if not _should_sync_model(sender):
        return
    try:
        if getattr(instance, "pk", None) is None:
            return
    except Exception:
        return

    from commerce.models import SyncQueue  # noqa: WPS433

    model_label = instance._meta.label
    payload = {}
    try:
        payload = serialize_instance(instance)
    except Exception:
        payload = {}

    def _enqueue() -> None:
        try:
            _enqueue_event(
                model_name=model_label,
                local_id=str(instance.pk),
                action=SyncQueue.Action.DELETE,
                payload=payload,
                using=using,
            )
        except Exception:
            logger.exception("Failed to enqueue delete sync event: %s#%s", model_label, getattr(instance, "pk", "?"))

    transaction.on_commit(_enqueue)


def register_desktop_sync_signals() -> None:
    """
    Register global desktop sync signals (desktop mode only).
    """
    global _REGISTERED  # noqa: PLW0603
    if _REGISTERED:
        return

    if not getattr(settings, "DESKTOP_MODE", False):
        return

    post_save.connect(_on_model_saved, dispatch_uid="desktop_sync_post_save")
    post_delete.connect(_on_model_deleted, dispatch_uid="desktop_sync_post_delete")
    _REGISTERED = True
    logger.info("Desktop sync signals registered (device_id=%s)", get_desktop_device_id())
