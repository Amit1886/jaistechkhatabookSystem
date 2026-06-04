import logging

logger = logging.getLogger(__name__)


def send_sms(to, message, *, purpose: str = "generic"):
    """
    Backward-compatible SMS sender.

    Uses unified Settings Center based gateway (`sms_center.sms_service.send_sms`),
    which also appends the customer login-link footer (if enabled).
    """
    try:
        from sms_center.sms_service import send_sms as send_sms_unified

        res = send_sms_unified(mobile=str(to or ""), text_message=str(message or ""), purpose=str(purpose or "generic"))
        status_code = int(res.get("status_code") or (200 if res.get("ok") else 0))
        response = res.get("response")
        if response is None:
            response = res.get("status") or ""
        return status_code, str(response)
    except Exception as exc:
        logger.exception("Unified SMS send failed")
        return 0, f"{type(exc).__name__}: {exc}"

