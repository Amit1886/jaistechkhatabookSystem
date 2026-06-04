from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from django.core.cache import cache
from django.utils import timezone


DEMO_PASSWORD = "DEMO_PASSWORD_CHANGE_ME"


def _cache_key(api_base: str, email: str) -> str:
    return f"shiprocket:token:{api_base.strip().rstrip('/')}:{email.strip().lower()}"


def _get_token(*, api_base: str, email: str, password: str) -> Optional[str]:
    url = api_base.rstrip("/") + "/v1/external/auth/login"
    resp = requests.post(url, json={"email": email, "password": password}, timeout=12)
    if not resp.ok:
        return None
    try:
        body: Any = resp.json()
    except Exception:
        return None
    return body.get("token") if isinstance(body, dict) else None


def get_token_cached(*, api_base: str, email: str, password: str) -> Optional[str]:
    """
    Returns Shiprocket auth token.

    Demo mode:
    - When password is a known placeholder (DEMO_PASSWORD_CHANGE_ME), returns "DEMO" without network calls.
    This keeps local demo flows working offline / without real credentials.
    """
    if str(password or "").strip() == DEMO_PASSWORD:
        return "DEMO"
    key = _cache_key(api_base, email)
    cached = cache.get(key)
    if cached:
        return cached
    token = _get_token(api_base=api_base, email=email, password=password)
    if token:
        # Token TTL can vary; use a safe default.
        cache.set(key, token, timeout=60 * 20)
    return token


def _assign_awb(*, api_base: str, token: str, shipment_id: Any) -> Dict[str, Any]:
    url = api_base.rstrip("/") + "/v1/external/courier/assign/awb"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(url, json={"shipment_id": shipment_id}, headers=headers, timeout=18)
    try:
        body: Any = resp.json()
    except Exception:
        body = resp.text
    if not resp.ok:
        return {"ok": False, "status": "assign_awb_failed", "status_code": resp.status_code, "response": body}
    # Usually contains awb_code + courier_name
    awb = ""
    courier_name = ""
    if isinstance(body, dict):
        awb = str(body.get("awb_code") or body.get("awb") or "").strip()
        courier_name = str(body.get("courier_name") or "").strip()
    return {"ok": True, "status": "assigned", "response": body, "awb_code": awb, "courier_name": courier_name}


def track_awb(*, api_base: str, token: str, awb: str) -> Dict[str, Any]:
    """
    Track a shipment by AWB.
    Uses: GET /v1/external/courier/track/awb/<awb>
    """
    awb = (awb or "").strip()
    if not awb:
        return {"ok": False, "status": "invalid_awb"}
    url = api_base.rstrip("/") + f"/v1/external/courier/track/awb/{awb}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=18)
    try:
        body: Any = resp.json()
    except Exception:
        body = resp.text
    if not resp.ok:
        return {"ok": False, "status": "provider_error", "status_code": resp.status_code, "response": body}
    return {"ok": True, "status": "ok", "response": body}


def create_shiprocket_shipment(*, order, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a Shiprocket order/shipment (best-effort minimal payload).

    Expected config keys:
    - email
    - password
    Optional:
    - api_base (default: https://apiv2.shiprocket.in)
    """
    api_base = str((config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
    email = str((config or {}).get("email") or "").strip()
    password = str((config or {}).get("password") or "").strip()

    mode = str((config or {}).get("mode") or "").strip().lower()
    demo_mode = mode == "demo" or password == DEMO_PASSWORD

    if demo_mode:
        # Deterministic fake ids (manifest print expects numeric order id).
        # Keep these stable per StoreOrder for easier testing.
        try:
            base_id = int(getattr(order, "id", 0) or 0)
        except Exception:
            base_id = 0
        shiprocket_order_id = str(100000 + base_id) if base_id else "100000"
        shipment_id = f"SR_DEMO_SHIP_{base_id or 'X'}"
        awb_code = f"DEMOAWB{base_id or 'X'}"
        return {
            "ok": True,
            "status": "created",
            "provider": "shiprocket",
            "external_ref": shipment_id,
            "shiprocket_order_id": shiprocket_order_id,
            "tracking_number": awb_code,
            "courier_name": "Shiprocket (DEMO)",
            "response": {"demo": True, "note": "Shiprocket demo mode: no external API calls were made."},
        }

    if not email or not password:
        return {"ok": False, "status": "not_configured", "error": "Missing Shiprocket email/password."}

    try:
        token = get_token_cached(api_base=api_base, email=email, password=password)
        if not token:
            return {"ok": False, "status": "auth_failed"}

        url = api_base.rstrip("/") + "/v1/external/orders/create/adhoc"
        address = getattr(order, "address", None)
        customer = getattr(order, "customer", None)
        items = getattr(order, "items", None)
        items_list = []
        if items is not None:
            for it in items.all():
                items_list.append(
                    {
                        "name": str(getattr(it.product, "name", "Item")),
                        "sku": str(getattr(it.product, "sku", "") or ""),
                        "units": int(getattr(it, "qty", 1) or 1),
                        "selling_price": str(getattr(it, "unit_price", "0") or "0"),
                    }
                )

        payload = {
            "order_id": str(getattr(order, "order_number", "") or str(getattr(order, "id", ""))),
            "order_date": str(getattr(order, "created_at", "") or ""),
            "pickup_location": str((config or {}).get("pickup_location") or "Primary"),
            "billing_customer_name": str(getattr(customer, "username", "") or getattr(customer, "email", "") or "Customer"),
            "billing_last_name": "",
            "billing_address": str(getattr(address, "line1", "") or ""),
            "billing_address_2": str(getattr(address, "line2", "") or ""),
            "billing_city": str(getattr(address, "district", "") or ""),
            "billing_pincode": str(getattr(address, "pincode", "") or ""),
            "billing_state": str(getattr(address, "state", "") or ""),
            "billing_country": "India",
            "billing_email": str(getattr(customer, "email", "") or ""),
            "billing_phone": str(getattr(customer, "mobile", "") or ""),
            "shipping_is_billing": True,
            "order_items": items_list,
            "payment_method": "Prepaid",
            "sub_total": str(getattr(order, "subtotal_amount", "0") or "0"),
            "length": (config or {}).get("length") or 10,
            "breadth": (config or {}).get("breadth") or 10,
            "height": (config or {}).get("height") or 5,
            "weight": (config or {}).get("weight") or 0.5,
        }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=18)
        try:
            body: Any = resp.json()
        except Exception:
            body = resp.text
        if not resp.ok:
            return {"ok": False, "status": "provider_error", "status_code": resp.status_code, "response": body}

        shipment_id = ""
        shiprocket_order_id = ""
        if isinstance(body, dict):
            shipment_id = str(body.get("shipment_id") or body.get("shipmentId") or body.get("shipment") or "").strip()
            shiprocket_order_id = str(body.get("order_id") or body.get("orderId") or "").strip()

        assign_res = {}
        awb_code = ""
        courier_name = ""
        if shipment_id:
            assign_res = _assign_awb(api_base=api_base, token=token, shipment_id=shipment_id)
            awb_code = str(assign_res.get("awb_code") or "").strip()
            courier_name = str(assign_res.get("courier_name") or "").strip()

        return {
            "ok": True,
            "status": "created",
            "provider": "shiprocket",
            "external_ref": shipment_id,
            "shiprocket_order_id": shiprocket_order_id,
            "tracking_number": awb_code or shipment_id,
            "courier_name": courier_name,
            "response": body,
            "assign_awb": assign_res,
        }
    except Exception as exc:
        return {"ok": False, "status": "exception", "error": str(exc)}


def generate_label(*, api_base: str, token: str, shipment_ids: list[str]) -> Dict[str, Any]:
    url = api_base.rstrip("/") + "/v1/external/courier/generate/label"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"shipment_id": [str(s) for s in shipment_ids if str(s).strip()]}
    resp = requests.post(url, json=body, headers=headers, timeout=18)
    try:
        data: Any = resp.json()
    except Exception:
        data = resp.text
    if not resp.ok:
        return {"ok": False, "status": "provider_error", "status_code": resp.status_code, "response": data}
    return {"ok": True, "status": "ok", "response": data}


def request_pickup(*, api_base: str, token: str, shipment_ids: list[str], pickup_date: str = "", retry: bool = False) -> Dict[str, Any]:
    """
    POST /v1/external/courier/generate/pickup
    - shipment_id must be passed as an array.
    - optional pickup_date: ["YYYY-MM-DD"]
    """
    url = api_base.rstrip("/") + "/v1/external/courier/generate/pickup"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body: Dict[str, Any] = {"shipment_id": [str(s) for s in shipment_ids if str(s).strip()]}
    if pickup_date:
        body["pickup_date"] = [pickup_date]
    if retry:
        body["status"] = "retry"
    resp = requests.post(url, json=body, headers=headers, timeout=24)
    try:
        data: Any = resp.json()
    except Exception:
        data = resp.text
    if not resp.ok:
        return {"ok": False, "status": "provider_error", "status_code": resp.status_code, "response": data}
    return {"ok": True, "status": "ok", "response": data}


def generate_manifest(*, api_base: str, token: str, shipment_ids: list[str]) -> Dict[str, Any]:
    """
    POST /v1/external/manifests/generate
    Shiprocket expects either shipment_id array (common) or order_ids array in some flows.
    We send shipment_id array by default.
    """
    url = api_base.rstrip("/") + "/v1/external/manifests/generate"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body: Dict[str, Any] = {"shipment_id": [str(s) for s in shipment_ids if str(s).strip()]}
    resp = requests.post(url, json=body, headers=headers, timeout=24)
    try:
        data: Any = resp.json()
    except Exception:
        data = resp.text
    if not resp.ok:
        return {"ok": False, "status": "provider_error", "status_code": resp.status_code, "response": data}
    return {"ok": True, "status": "ok", "response": data}


def print_manifest(*, api_base: str, token: str, order_ids: list[str]) -> Dict[str, Any]:
    """
    POST /v1/external/manifests/print
    Requires Shiprocket order_ids array.
    """
    url = api_base.rstrip("/") + "/v1/external/manifests/print"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body: Dict[str, Any] = {"order_ids": [int(o) for o in order_ids if str(o).strip().isdigit()]}
    resp = requests.post(url, json=body, headers=headers, timeout=24)
    try:
        data: Any = resp.json()
    except Exception:
        data = resp.text
    if not resp.ok:
        return {"ok": False, "status": "provider_error", "status_code": resp.status_code, "response": data}
    return {"ok": True, "status": "ok", "response": data}
