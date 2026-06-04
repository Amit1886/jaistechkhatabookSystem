from __future__ import annotations

import base64
from decimal import Decimal
from typing import Any, Dict

import requests


def _basic_auth_header(key_id: str, key_secret: str) -> str:
    raw = f"{key_id}:{key_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def initiate_razorpay_payment(*, order, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a Razorpay Order via REST API.

    Expected config keys:
    - key_id
    - key_secret
    Optional:
    - api_base (default: https://api.razorpay.com)
    """
    key_id = str((config or {}).get("key_id") or "").strip()
    key_secret = str((config or {}).get("key_secret") or "").strip()
    if not key_id or not key_secret:
        return {"ok": False, "status": "not_configured", "error": "Missing Razorpay key_id/key_secret."}

    api_base = str((config or {}).get("api_base") or "https://api.razorpay.com").strip().rstrip("/")
    url = api_base + "/v1/orders"

    amount_inr = Decimal(str(getattr(order, "total_amount", "0") or "0"))
    amount_paise = int((amount_inr * Decimal("100")).quantize(Decimal("1")))
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": str(getattr(order, "order_number", "") or str(getattr(order, "id", ""))),
        "notes": {"store_order_id": str(getattr(order, "id", ""))},
    }
    headers = {
        "Authorization": _basic_auth_header(key_id, key_secret),
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=12)
        try:
            body: Any = resp.json()
        except Exception:
            body = resp.text
        if not resp.ok:
            return {"ok": False, "status": "provider_error", "status_code": resp.status_code, "response": body}
        return {
            "ok": True,
            "status": "created",
            "provider": "razorpay",
            "razorpay_order": body,
            "key_id": key_id,  # safe to return (public identifier)
        }
    except Exception as exc:
        return {"ok": False, "status": "exception", "error": str(exc)}

