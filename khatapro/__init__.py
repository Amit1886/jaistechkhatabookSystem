from __future__ import annotations

import os
import sys


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


IS_FROZEN = bool(getattr(sys, "frozen", False))
DESKTOP_MODE = IS_FROZEN or _truthy(os.getenv("DESKTOP_MODE"))
DISABLE_CELERY = DESKTOP_MODE or _truthy(os.getenv("DISABLE_CELERY"))

celery_app = None
if not DISABLE_CELERY:
    try:
        from .celery import app as celery_app  # type: ignore
    except Exception:
        # Celery is optional; do not crash Django startup if Celery isn't available.
        celery_app = None

__all__ = ("celery_app",)
