from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class GatewayResponse:
    ok: bool
    status_code: int
    text: str
    data: Any


def _base_url() -> str:
    return (os.getenv("WA_GATEWAY_BASE_URL") or "").rstrip("/")


def _api_key() -> str:
    return (os.getenv("WA_GATEWAY_API_KEY") or "").strip()


def _session_id() -> str:
    return (os.getenv("WA_SESSION_ID") or "default").strip()


def _headers() -> dict[str, str]:
    key = _api_key()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}" if key else "",
    }


def request_qr(*, webhook_url: str = "", webhook_secret: str = "", timeout_ms: int = 25000) -> GatewayResponse:
    url = f"{_base_url()}/sessions/qr"
    payload: dict[str, Any] = {"session_id": _session_id(), "timeout_ms": int(timeout_ms)}
    if webhook_url:
        payload["webhook_url"] = webhook_url
    if webhook_secret:
        payload["webhook_secret"] = webhook_secret
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    # This endpoint returns plain text (data:image... or "connected")
    return GatewayResponse(ok=resp.ok, status_code=resp.status_code, text=resp.text, data=None)


def send_message(*, phone: str, message: str) -> GatewayResponse:
    url = f"{_base_url()}/send-message"
    resp = requests.post(
        url,
        json={"session_id": _session_id(), "phone": phone, "message": message},
        headers=_headers(),
        timeout=30,
    )
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
    return GatewayResponse(ok=resp.ok, status_code=resp.status_code, text=resp.text, data=data)


def send_bulk(*, numbers: list[str], message: str) -> GatewayResponse:
    url = f"{_base_url()}/send-bulk"
    resp = requests.post(
        url,
        json={"session_id": _session_id(), "numbers": numbers, "message": message},
        headers=_headers(),
        timeout=120,
    )
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
    return GatewayResponse(ok=resp.ok, status_code=resp.status_code, text=resp.text, data=data)

