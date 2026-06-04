from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import requests
from django.conf import settings

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WhatsAppSendResult:
    ok: bool
    status_code: int
    response_text: str
    provider: str


def _get_global_setting(key: str, default: Any = "") -> Any:
    try:
        sync_settings_registry()
    except Exception:
        pass
    try:
        definition = SettingDefinition.objects.filter(key=key).first()
        if not definition:
            return default
        value_obj = SettingValue.objects.filter(definition=definition, owner__isnull=True).first()
        return value_obj.value if value_obj else definition.default_value
    except Exception:
        return default


def whatsapp_enabled() -> bool:
    val = _get_global_setting("wa_enabled", True)
    try:
        return bool(val)
    except Exception:
        return True


def send_whatsapp_message(*, to: str, message: str, from_number: str = "", purpose: str = "generic") -> WhatsAppSendResult:
    """
    Provider-agnostic WhatsApp sender.

    Supported providers:
    - UltraMsg
    - Meta WhatsApp Cloud API
    - Twilio WhatsApp
    - Custom HTTP (generic adapter)
    """
    provider = str(_get_global_setting("wa_provider", "ultramsg") or "ultramsg").strip().lower()
    if not whatsapp_enabled():
        return WhatsAppSendResult(ok=False, status_code=403, response_text="WhatsApp automation disabled", provider=provider)

    to = (to or "").strip().lstrip("+")
    message = (message or "").strip()
    if not to or not message:
        return WhatsAppSendResult(ok=False, status_code=400, response_text="Missing to/message", provider=provider)

    try:
        from core_settings.customer_login_link import maybe_append_customer_login_link

        message = maybe_append_customer_login_link(
            channel="whatsapp", recipient=str(to or ""), message=str(message or ""), purpose=str(purpose or "generic")
        )
    except Exception:
        pass

    if provider == "ultramsg":
        instance_id = str(_get_global_setting("wa_ultramsg_instance_id", "") or "").strip()
        token = str(_get_global_setting("wa_ultramsg_token", "") or "").strip()
        if not instance_id or not token:
            return WhatsAppSendResult(ok=False, status_code=400, response_text="UltraMsg not configured", provider=provider)

        url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
        payload = {"to": to, "body": message}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {token}",
        }
        try:
            resp = requests.post(url, data=payload, headers=headers, timeout=20)
            return WhatsAppSendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text, provider=provider)
        except Exception as e:
            logger.exception("WhatsApp send failed")
            return WhatsAppSendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}", provider=provider)

    if provider == "meta_cloud_api":
        phone_number_id = str(_get_global_setting("wa_meta_phone_number_id", "") or "").strip()
        access_token = str(_get_global_setting("wa_meta_access_token", "") or "").strip()
        version = str(_get_global_setting("wa_meta_graph_version", "v20.0") or "v20.0").strip()
        if not phone_number_id or not access_token:
            return WhatsAppSendResult(ok=False, status_code=400, response_text="Meta Cloud API not configured", provider=provider)

        # Meta expects international number (digits). Keep existing normalization.
        url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            return WhatsAppSendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text, provider=provider)
        except Exception as e:
            logger.exception("WhatsApp send failed")
            return WhatsAppSendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}", provider=provider)

    if provider == "twilio":
        account_sid = str(_get_global_setting("wa_twilio_account_sid", "") or "").strip()
        auth_token = str(_get_global_setting("wa_twilio_auth_token", "") or "").strip()
        tw_from = str(_get_global_setting("wa_twilio_from_number", "") or "").strip()
        if not account_sid or not auth_token or not tw_from:
            return WhatsAppSendResult(ok=False, status_code=400, response_text="Twilio not configured", provider=provider)

        if not tw_from.lower().startswith("whatsapp:"):
            tw_from = f"whatsapp:{tw_from}"
        tw_to = to
        if not tw_to.lower().startswith("whatsapp:"):
            tw_to = f"whatsapp:+{tw_to}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        payload = {"From": tw_from, "To": tw_to, "Body": message}
        try:
            resp = requests.post(url, data=payload, auth=(account_sid, auth_token), timeout=20)
            return WhatsAppSendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text, provider=provider)
        except Exception as e:
            logger.exception("WhatsApp send failed")
            return WhatsAppSendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}", provider=provider)

    # Default fallback for other market providers: Custom HTTP adapter.
    send_url = str(_get_global_setting("wa_custom_send_url", "") or "").strip()
    if not send_url:
        return WhatsAppSendResult(ok=False, status_code=400, response_text=f"Unsupported provider '{provider}' (set provider=custom_http + configure custom send URL)", provider=provider)

    content_type = str(_get_global_setting("wa_custom_content_type", "form") or "form").strip().lower()
    to_field = str(_get_global_setting("wa_custom_to_field", "to") or "to").strip() or "to"
    body_field = str(_get_global_setting("wa_custom_body_field", "body") or "body").strip() or "body"
    headers = _get_global_setting("wa_custom_headers", {}) or {}
    if not isinstance(headers, dict):
        headers = {}
    auth_header = str(_get_global_setting("wa_custom_auth_header", "Authorization") or "Authorization").strip() or "Authorization"
    auth_value = str(_get_global_setting("wa_custom_auth_value", "") or "").strip()
    if auth_value:
        headers[auth_header] = auth_value

    extra_payload = _get_global_setting("wa_custom_extra_payload", {}) or {}
    if not isinstance(extra_payload, dict):
        extra_payload = {}

    payload = {to_field: to, body_field: message}
    if from_number:
        # Optional hint for providers that accept a sender field in payload via extra config.
        payload.setdefault("from", str(from_number).strip())
    payload.update(extra_payload)

    try:
        if content_type == "json":
            resp = requests.post(send_url, json=payload, headers=headers, timeout=20)
        else:
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            resp = requests.post(send_url, data=payload, headers=headers, timeout=20)
        return WhatsAppSendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text, provider=provider)
    except Exception as e:
        logger.exception("WhatsApp send failed")
        return WhatsAppSendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}", provider=provider)


def verify_webhook_secret(provided: Optional[str]) -> bool:
    secret = str(_get_global_setting("wa_webhook_secret", "") or "").strip()
    if not secret:
        # Security default: do not accept webhook without a configured secret.
        return False
    return bool(provided) and provided == secret
