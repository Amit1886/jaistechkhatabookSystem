from __future__ import annotations

from typing import Any, Dict


def initiate_payment(*, order, provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
    provider = (provider or "").strip().lower()
    if provider == "razorpay":
        from .razorpay import initiate_razorpay_payment

        return initiate_razorpay_payment(order=order, config=config)
    if provider in {"stripe", "paytm"}:
        return {"ok": False, "status": "not_implemented", "provider": provider}
    if provider in {"dummy", "manual", ""}:
        return {"ok": True, "status": "noop", "provider": provider or "dummy"}
    return {"ok": False, "status": "unsupported_provider", "provider": provider}

