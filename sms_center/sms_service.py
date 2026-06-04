import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from .models import SMSProviderSettings

logger = logging.getLogger(__name__)


def _get_global_setting(key: str, default: Any = "") -> Any:
    try:
        from core_settings.models import SettingDefinition, SettingValue
        from core_settings.services import sync_settings_registry

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


def _get_google_credentials() -> tuple[str, str]:
    # Prefer unified Settings Center values if provided.
    api_key = str(_get_global_setting("sms_api_key", "") or "").strip()
    sender_id = str(_get_global_setting("sms_sender_id", "") or "").strip()

    provider = None
    try:
        provider = SMSProviderSettings.objects.filter(provider=SMSProviderSettings.Provider.GOOGLE, is_active=True).first()
    except Exception:
        provider = None

    api_key = api_key or (getattr(provider, "api_key", "") or "").strip() or (getattr(settings, "GOOGLE_SMS_API_KEY", "") or "").strip()
    sender_id = sender_id or (getattr(provider, "sender_id", "") or "").strip() or (getattr(settings, "GOOGLE_SMS_SENDER_ID", "") or "").strip()
    return api_key, sender_id


def send_google_sms(
    mobile: str,
    text_message: str,
    image_url: Optional[str] = None,
    *,
    api_key: str | None = None,
    sender_id: str | None = None,
    api_url: str | None = None,
) -> Dict[str, Any]:
    """
    Send SMS via a Google Verified SMS / RCS gateway.

    Notes:
    - Google Verified SMS is typically accessed through partner gateways.
    - This implementation supports an override endpoint via settings.GOOGLE_SMS_API_URL.
    """
    mobile = (mobile or "").strip()
    text_message = (text_message or "").strip()

    api_key = (api_key or "").strip() or _get_google_credentials()[0]
    sender_id = (sender_id or "").strip() or _get_google_credentials()[1]
    if not api_key or not sender_id:
        return {
            "ok": False,
            "status": "not_configured",
            "error": "Missing GOOGLE_SMS_API_KEY/GOOGLE_SMS_SENDER_ID (or active SMSProviderSettings).",
        }

    api_url = (
        (api_url or "").strip()
        or str(_get_global_setting("sms_api_url", "") or "").strip()
        or (getattr(settings, "GOOGLE_SMS_API_URL", "") or "").strip()
    )
    if not api_url:
        # Default to a placeholder endpoint; most deployments should override this.
        api_url = "https://verifiedsms.googleapis.com/v1/messages:send"

    payload: Dict[str, Any] = {
        "to": mobile,
        "sender_id": sender_id,
        "message": text_message,
    }
    if image_url:
        payload["image_url"] = image_url

    headers = {
        "Content-Type": "application/json",
        # Support common API-key header conventions.
        "X-API-KEY": api_key,
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=10)
        content_type = (resp.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            body: Any = resp.json()
        else:
            body = resp.text
        return {
            "ok": resp.ok,
            "status_code": resp.status_code,
            "response": body,
        }
    except Exception as exc:
        logger.exception("Google SMS send failed")
        return {
            "ok": False,
            "status": "exception",
            "error": str(exc),
        }


def _normalize_digits(value: str) -> str:
    try:
        from whatsapp.services.phone import digits_only

        return digits_only(value)
    except Exception:
        return "".join([c for c in (value or "") if c.isdigit()]).strip()


def send_fast2sms_sms(mobile: str, text_message: str, *, purpose: str = "generic") -> Dict[str, Any]:
    mobile = _normalize_digits(mobile)
    text_message = (text_message or "").strip()
    if not mobile or not text_message:
        return {"ok": False, "status": "invalid_args"}

    api_key = str(_get_global_setting("sms_api_key", "") or "").strip() or getattr(settings, "FAST2SMS_API_KEY", None)
    if not api_key:
        return {"ok": False, "status": "not_configured", "error": "Missing sms_api_key / FAST2SMS_API_KEY."}

    sender_id = str(_get_global_setting("sms_sender_id", "") or "").strip()
    dlt_enabled = bool(_get_global_setting("sms_dlt_enabled", False))
    template_id = ""
    entity_id = ""
    if dlt_enabled and purpose == "otp":
        entity_id = str(_get_global_setting("sms_dlt_entity_id", "") or "").strip()
        template_id = str(_get_global_setting("sms_dlt_template_id_otp", "") or "").strip()

    # Keep the existing Fast2SMS pattern (GET) to stay compatible with this repo.
    # NOTE: Providers may require URL encoding for message; keep it simple via requests params.
    url = "https://www.fast2sms.com/dev/bulkV2"
    params: Dict[str, Any] = {
        "authorization": api_key,
        "route": "q",
        "message": text_message,
        "language": "english",
        "flash": "0",
        "numbers": mobile,
    }
    if sender_id:
        params["sender_id"] = sender_id
    if entity_id:
        params["entity_id"] = entity_id
    if template_id:
        params["template_id"] = template_id

    try:
        resp = requests.get(url, params=params, headers={"cache-control": "no-cache"}, timeout=20)
        return {"ok": resp.ok, "status_code": resp.status_code, "response": resp.text}
    except Exception as exc:
        logger.exception("Fast2SMS send failed")
        return {"ok": False, "status": "exception", "error": str(exc)}


def send_custom_http_sms(mobile: str, text_message: str, *, purpose: str = "generic") -> Dict[str, Any]:
    mobile = _normalize_digits(mobile)
    text_message = (text_message or "").strip()
    if not mobile or not text_message:
        return {"ok": False, "status": "invalid_args"}

    send_url = str(_get_global_setting("sms_custom_send_url", "") or "").strip() or str(_get_global_setting("sms_api_url", "") or "").strip()
    if not send_url:
        return {"ok": False, "status": "not_configured", "error": "Missing sms_custom_send_url / sms_api_url."}

    method = str(_get_global_setting("sms_custom_method", "POST") or "POST").strip().upper()
    content_type = str(_get_global_setting("sms_custom_content_type", "form") or "form").strip().lower()
    to_field = str(_get_global_setting("sms_custom_to_field", "to") or "to").strip() or "to"
    message_field = str(_get_global_setting("sms_custom_message_field", "message") or "message").strip() or "message"

    headers = _get_global_setting("sms_custom_headers", {}) or {}
    if not isinstance(headers, dict):
        headers = {}

    auth_header = str(_get_global_setting("sms_custom_auth_header", "Authorization") or "Authorization").strip() or "Authorization"
    auth_value = str(_get_global_setting("sms_custom_auth_value", "") or "").strip()
    if auth_value:
        headers[auth_header] = auth_value

    extra_payload = _get_global_setting("sms_custom_extra_payload", {}) or {}
    if not isinstance(extra_payload, dict):
        extra_payload = {}

    payload: Dict[str, Any] = {to_field: mobile, message_field: text_message}

    sender_id = str(_get_global_setting("sms_sender_id", "") or "").strip()
    if sender_id:
        payload.setdefault("sender_id", sender_id)

    dlt_enabled = bool(_get_global_setting("sms_dlt_enabled", False))
    if dlt_enabled and purpose == "otp":
        entity_id = str(_get_global_setting("sms_dlt_entity_id", "") or "").strip()
        template_id = str(_get_global_setting("sms_dlt_template_id_otp", "") or "").strip()
        if entity_id:
            payload.setdefault("entity_id", entity_id)
        if template_id:
            payload.setdefault("template_id", template_id)

    payload.update(extra_payload)

    try:
        if method == "GET":
            resp = requests.get(send_url, params=payload, headers=headers, timeout=20)
        else:
            if content_type == "json":
                resp = requests.post(send_url, json=payload, headers=headers, timeout=20)
            else:
                headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
                resp = requests.post(send_url, data=payload, headers=headers, timeout=20)
        return {"ok": resp.ok, "status_code": resp.status_code, "response": resp.text}
    except Exception as exc:
        logger.exception("Custom SMS send failed")
        return {"ok": False, "status": "exception", "error": str(exc)}


def send_sms(
    mobile: str,
    text_message: str,
    *,
    purpose: str = "generic",
    image_url: Optional[str] = None,
    provider_override: str | None = None,
) -> Dict[str, Any]:
    """
    Unified SMS sender configured from Settings Center.

    Providers supported:
    - fast2sms
    - google (Verified SMS via gateway)
    - custom_http
    """
    try:
        from core_settings.customer_login_link import maybe_append_customer_login_link

        text_message = maybe_append_customer_login_link(
            channel="sms", recipient=str(mobile or ""), message=str(text_message or ""), purpose=str(purpose or "generic")
        )
    except Exception:
        pass

    provider = (provider_override or "").strip().lower() or str(_get_global_setting("sms_provider", "fast2sms") or "fast2sms").strip().lower()

    if provider == "demo":
        # Local/demo mode: treat as sent without calling any external API.
        return {"ok": True, "status": "demo_sent"}
    if provider == "google":
        return send_google_sms(mobile=mobile, text_message=text_message, image_url=image_url)
    if provider == "custom_http":
        return send_custom_http_sms(mobile=mobile, text_message=text_message, purpose=purpose)
    if provider == "fast2sms":
        return send_fast2sms_sms(mobile=mobile, text_message=text_message, purpose=purpose)

    return {"ok": False, "status": "not_configured", "error": f"Unsupported sms_provider '{provider}'"}
