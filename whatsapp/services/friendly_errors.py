from __future__ import annotations

import json


_FRIENDLY: dict[str, str] = {
    # Gateway auth/config
    "gateway_api_key_not_configured": "Gateway API key not configured (set GATEWAY_API_KEY in whatsapp_gateway/.env).",
    "unauthorized": "Unauthorized (Gateway API key mismatch).",
    # Session
    "missing_session_id": "Missing session id (create/request QR first).",
    "invalid_session_id": "Invalid session id (request QR again).",
    "session_not_started": "Session not started (request QR and scan).",
    "not_ready": "Session not ready (scan QR and wait until connected).",
    "logged_out": "Logged out (request QR and scan again).",
    # Messaging
    "invalid_phone": "Invalid phone number (use country code).",
    "empty_message": "Empty message.",
}


def extract_error(text: str) -> str:
    """
    Extract a meaningful error string from provider responses.

    - Web Gateway often returns JSON: {"ok":false,"error":"not_ready"}
    - QR endpoint may return plain text (e.g. "missing_session_id")
    """
    raw = (text or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except Exception:
        return raw

    if isinstance(parsed, dict):
        for k in ("error", "message", "detail"):
            v = parsed.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return raw


def friendly_error(text: str) -> str:
    err = extract_error(text)
    key = err.strip()
    low = key.lower()

    # Connection refused / gateway not running (common Windows error)
    if (
        "winerror 10061" in low
        or "actively refused" in low
        or "connection refused" in low
        or ("max retries exceeded" in low and "127.0.0.1" in low and "3100" in low)
    ):
        return (
            "Gateway is OFFLINE. In local dev, it should auto-start when you run `python manage.py runserver`. "
            "If it stays offline, click 'Restart Gateway Service' in the wizard or start it manually: `cd whatsapp_gateway && npm run start`."
        )

    # Puppeteer/Chrome launch issues
    if "spawn eperm" in low or "no open browser" in low:
        return (
            "Gateway cannot open browser (Puppeteer). Install Google Chrome and set `PUPPETEER_EXECUTABLE_PATH` "
            "in whatsapp_gateway/.env, then restart the gateway."
        )

    if "readtimeout" in low or ("read timed out" in low and "httpconnectionpool" in low):
        return (
            "Gateway took too long to respond while generating QR. Check `whatsapp_gateway/gateway_supervisor.log` "
            "for Puppeteer/Chrome errors, and ensure Chrome is installed (set `PUPPETEER_EXECUTABLE_PATH`)."
        )

    if "create_timeout_" in low:
        return (
            "Gateway session startup timed out (Puppeteer/Chrome did not start). "
            "Install/update Google Chrome and set `PUPPETEER_EXECUTABLE_PATH` in `whatsapp_gateway/.env`, then restart the gateway."
        )

    return _FRIENDLY.get(key, err)
