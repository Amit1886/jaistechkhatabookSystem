from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from jose import jwt
except Exception:  # pragma: no cover - fallback for existing environments before pip install
    import jwt  # type: ignore

from django.conf import settings


JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_MINUTES = int(os.getenv("FASTAPI_ACCESS_TOKEN_MINUTES", "30"))
REFRESH_DAYS = int(os.getenv("FASTAPI_REFRESH_TOKEN_DAYS", "7"))


def jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or getattr(settings, "SECRET_KEY", "dev-secret-key")


def create_token(*, subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        **(extra or {}),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGORITHM)


def create_access_token(*, user, tenant_id: str = "", company_id: str = "") -> str:
    return create_token(
        subject=str(user.pk),
        token_type="access",
        expires_delta=timedelta(minutes=ACCESS_MINUTES),
        extra={"tenant_id": tenant_id, "company_id": company_id},
    )


def create_refresh_token(*, user) -> str:
    return create_token(
        subject=str(user.pk),
        token_type="refresh",
        expires_delta=timedelta(days=REFRESH_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, jwt_secret(), algorithms=[JWT_ALGORITHM])
