from __future__ import annotations

from typing import Any, Dict


def create_shipment(*, order, provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
    provider = (provider or "").strip().lower()
    if provider == "shiprocket":
        from .shiprocket import create_shiprocket_shipment

        return create_shiprocket_shipment(order=order, config=config)
    if provider in {"delhivery", "bluedart"}:
        return {"ok": False, "status": "not_implemented", "provider": provider}
    if provider in {"manual", ""}:
        return {"ok": True, "status": "noop", "provider": provider or "manual"}
    return {"ok": False, "status": "unsupported_provider", "provider": provider}


def track_shipment(*, provider: str, config: Dict[str, Any], tracking_number: str) -> Dict[str, Any]:
    provider = (provider or "").strip().lower()
    if provider == "shiprocket":
        from .shiprocket import get_token_cached, track_awb

        api_base = str((config or {}).get("api_base") or "https://apiv2.shiprocket.in").strip()
        email = str((config or {}).get("email") or "").strip()
        password = str((config or {}).get("password") or "").strip()
        if not email or not password:
            return {"ok": False, "status": "not_configured"}
        token = get_token_cached(api_base=api_base, email=email, password=password)
        if not token:
            return {"ok": False, "status": "auth_failed"}
        return track_awb(api_base=api_base, token=token, awb=tracking_number)
    return {"ok": False, "status": "unsupported_provider", "provider": provider}
