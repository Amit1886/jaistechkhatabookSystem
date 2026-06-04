from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


_FERNET: Optional[Fernet] = None
_PREFIX = "enc:"


def _derive_fernet_key(material: str) -> bytes:
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    """
    Returns a process-level Fernet instance.

    Uses (in order):
    - WA_ENCRYPTION_KEY (either a valid Fernet key or any string material)
    - DJANGO_SECRET_KEY/SECRET_KEY derived key
    """
    global _FERNET
    if _FERNET is not None:
        return _FERNET

    raw = (os.getenv("WA_ENCRYPTION_KEY") or "").strip()
    if raw:
        try:
            # If it's already a valid Fernet key, this will succeed.
            _FERNET = Fernet(raw.encode("utf-8"))
            return _FERNET
        except Exception:
            _FERNET = Fernet(_derive_fernet_key(raw))
            return _FERNET

    secret = (getattr(settings, "SECRET_KEY", None) or os.getenv("DJANGO_SECRET_KEY") or "").strip()
    if not secret:
        # Dev-safe fallback (still deterministic) to avoid crashing imports.
        secret = "dev-secret"
    _FERNET = Fernet(_derive_fernet_key(secret + "|whatsapp"))
    return _FERNET


def is_encrypted(value: str | None) -> bool:
    return bool(value) and str(value).startswith(_PREFIX)


def encrypt_str(value: str | None) -> str:
    value = "" if value is None else str(value)
    if not value:
        return ""
    if is_encrypted(value):
        return value
    token = get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return _PREFIX + token


def decrypt_str(value: str | None) -> str:
    value = "" if value is None else str(value)
    if not value:
        return ""
    if not is_encrypted(value):
        return value
    token = value[len(_PREFIX) :]
    try:
        return get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # If the key was rotated, keep data non-fatal but unreadable.
        return ""

