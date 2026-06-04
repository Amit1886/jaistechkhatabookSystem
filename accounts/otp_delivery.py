from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.mail import EmailMessage, get_connection, send_mail

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry

logger = logging.getLogger(__name__)


def _get_global_setting(key: str, default: Any = "") -> Any:
    try:
        try:
            sync_settings_registry()
        except Exception:
            pass
        definition = SettingDefinition.objects.filter(key=key).first()
        if not definition:
            return default
        value_obj = SettingValue.objects.filter(definition=definition, owner__isnull=True).first()
        return value_obj.value if value_obj else definition.default_value
    except Exception:
        return default


def _bool_setting(key: str, default: bool) -> bool:
    v = _get_global_setting(key, default)
    try:
        return bool(v)
    except Exception:
        return default


def _normalize_whatsapp_to(value: str) -> str:
    try:
        from whatsapp.services.phone import normalize_wa_phone

        cc = str(getattr(settings, "WA_DEFAULT_COUNTRY_CODE", "") or "").strip()
        return normalize_wa_phone(value, default_country_code=cc)
    except Exception:
        return "".join([c for c in (value or "") if c.isdigit()]).strip()


def _send_email_otp(*, to_email: str, code: str) -> Dict[str, Any]:
    to_email = (to_email or "").strip()
    code = (code or "").strip()
    if not to_email or not code:
        return {"ok": False, "status": "invalid_args"}

    subject = "Your OTP Code"
    body = f"Your verification code is: {code}"
    from_email = (str(_get_global_setting("smtp_from_email", "") or "").strip() or getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()

    smtp_host = str(_get_global_setting("smtp_host", "") or "").strip()
    if not smtp_host:
        # Fall back to Django's configured email backend.
        try:
            send_mail(subject, body, from_email, [to_email], fail_silently=True)
            return {"ok": True, "status": "sent"}
        except Exception as exc:
            logger.exception("OTP email send failed")
            return {"ok": False, "status": "exception", "error": str(exc)}

    try:
        smtp_port = int(_get_global_setting("smtp_port", 587) or 587)
    except Exception:
        smtp_port = 587
    username = str(_get_global_setting("smtp_username", "") or "").strip()
    password = str(_get_global_setting("smtp_password", "") or "").strip()
    use_tls = _bool_setting("smtp_use_tls", True)
    use_ssl = _bool_setting("smtp_use_ssl", False)
    if use_ssl:
        use_tls = False

    try:
        connection = get_connection(
            host=smtp_host,
            port=smtp_port,
            username=username or None,
            password=password or None,
            use_tls=use_tls,
            use_ssl=use_ssl,
            fail_silently=True,
        )
        msg = EmailMessage(subject=subject, body=body, from_email=from_email, to=[to_email], connection=connection)
        sent = msg.send(fail_silently=True)
        return {"ok": bool(sent), "status": "sent" if sent else "failed"}
    except Exception as exc:
        logger.exception("OTP email send failed")
        return {"ok": False, "status": "exception", "error": str(exc)}


def _send_sms_otp(*, to_mobile: str, code: str) -> Dict[str, Any]:
    code = (code or "").strip()
    if not to_mobile or not code:
        return {"ok": False, "status": "invalid_args"}

    message = f"Your OTP is {code}. Do not share this OTP."
    try:
        from sms_center.sms_service import send_sms

        return send_sms(mobile=to_mobile, text_message=message, purpose="otp")
    except Exception as exc:
        logger.exception("OTP SMS send failed")
        return {"ok": False, "status": "exception", "error": str(exc)}


def _send_whatsapp_otp(*, to_whatsapp: str, code: str) -> Dict[str, Any]:
    code = (code or "").strip()
    if not to_whatsapp or not code:
        return {"ok": False, "status": "invalid_args"}

    to_norm = _normalize_whatsapp_to(to_whatsapp)
    if not to_norm:
        return {"ok": False, "status": "invalid_args"}

    message = f"Your OTP is {code}. Do not share this OTP."
    try:
        from whatsapp.api_connector import send_whatsapp_message

        res = send_whatsapp_message(to=to_norm, message=message)
        return {"ok": bool(res.ok), "status_code": res.status_code, "provider": res.provider, "response": res.response_text}
    except Exception as exc:
        logger.exception("OTP WhatsApp send failed")
        return {"ok": False, "status": "exception", "error": str(exc)}


def send_otp_code(*, to_email: Optional[str], to_mobile: Optional[str], code: str) -> Dict[str, Any]:
    """
    Send OTP via configured channels (SMS + Email + WhatsApp).

    Configuration is in Settings Center -> WhatsApp & Communication:
    - otp_delivery_strategy: all|fallback
    - otp_send_via_sms / otp_send_via_email / otp_send_via_whatsapp
    """
    strategy = str(_get_global_setting("otp_delivery_strategy", "all") or "all").strip().lower()
    via_sms = _bool_setting("otp_send_via_sms", True)
    via_email = _bool_setting("otp_send_via_email", True)
    via_whatsapp = _bool_setting("otp_send_via_whatsapp", True)

    results: Dict[str, Any] = {"strategy": strategy, "channels": {}}

    # For WhatsApp, default to the same number as SMS if not explicitly provided.
    to_whatsapp = to_mobile

    def _ok(res: Dict[str, Any]) -> bool:
        return bool(res.get("ok"))

    if strategy == "fallback":
        if via_sms and to_mobile:
            r = _send_sms_otp(to_mobile=to_mobile, code=code)
            results["channels"]["sms"] = r
            if _ok(r):
                return results
        if via_email and to_email:
            r = _send_email_otp(to_email=to_email, code=code)
            results["channels"]["email"] = r
            if _ok(r):
                return results
        if via_whatsapp and to_whatsapp:
            r = _send_whatsapp_otp(to_whatsapp=to_whatsapp, code=code)
            results["channels"]["whatsapp"] = r
            return results
        return results

    # Default: send via all enabled channels (best reliability).
    if via_email and to_email:
        results["channels"]["email"] = _send_email_otp(to_email=to_email, code=code)
    if via_sms and to_mobile:
        results["channels"]["sms"] = _send_sms_otp(to_mobile=to_mobile, code=code)
    if via_whatsapp and to_whatsapp:
        results["channels"]["whatsapp"] = _send_whatsapp_otp(to_whatsapp=to_whatsapp, code=code)

    return results

