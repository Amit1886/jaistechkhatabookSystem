from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMessage, get_connection, send_mail


@dataclass(frozen=True)
class SendResult:
    ok: bool
    provider: str = ""
    error: str = ""


def _vendor_provider_cfg(vendor, key: str):
    try:
        from vendors.models import VendorMarketingProviderConfig

        return VendorMarketingProviderConfig.objects.filter(vendor=vendor, provider=key).first()
    except Exception:
        return None


def _get_global_setting(key: str, default: object = "") -> object:
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


def vendor_channel_enabled(vendor, key: str) -> bool:
    cfg = _vendor_provider_cfg(vendor, key)
    if cfg is None:
        return False
    return bool(getattr(cfg, "is_active", False))


def send_vendor_whatsapp(*, vendor, to: str, message: str) -> SendResult:
    """
    WhatsApp sender (best effort):
    - If vendor owner has a connected WhatsAppAccount, use provider_clients (preferred for per-vendor accounts).
    - Else fallback to global whatsapp.api_connector (uses global settings center).
    """
    to = (to or "").strip()
    message = (message or "").strip()
    if not to or not message:
        return SendResult(ok=False, provider="whatsapp", error="Missing to/message")

    cfg = _vendor_provider_cfg(vendor, "whatsapp")
    cfg_blob = (cfg.config if cfg else {}) or {}
    from_number = str(cfg_blob.get("from_number") or "").strip()

    # Preferred: vendor-specific WhatsApp accounts (if set up).
    try:
        account = (
            vendor.owner.whatsapp_accounts.filter(is_active=True)
            .exclude(status__in=["disabled", "error"])
            .order_by("-last_seen_at", "-updated_at")
            .first()
        )
    except Exception:
        account = None

    if account:
        try:
            from whatsapp.services.provider_clients import send_text

            res = send_text(account=account, to=to, text=message)
            return SendResult(ok=bool(res.ok), provider=str(res.provider or "whatsapp"), error=str(res.response_text or "") if not res.ok else "")
        except Exception as exc:
            # fall through to global connector
            last_err = f"{type(exc).__name__}: {exc}"
        else:
            last_err = ""
    else:
        last_err = ""

    # Fallback: global connector (UltraMsg/Meta/Twilio/custom_http based on Settings Center).
    try:
        from whatsapp.api_connector import send_whatsapp_message

        res = send_whatsapp_message(to=to, message=message, from_number=from_number)
        return SendResult(ok=bool(res.ok), provider=str(res.provider or "whatsapp"), error=str(res.response_text or "") if not res.ok else "")
    except Exception as exc:
        return SendResult(ok=False, provider="whatsapp", error=last_err or f"{type(exc).__name__}: {exc}")


def send_vendor_sms(*, vendor, to: str, message: str) -> SendResult:
    """
    SMS sender with per-vendor overrides (google/fast2sms/custom_http).
    """
    to = (to or "").strip()
    message = (message or "").strip()
    if not to or not message:
        return SendResult(ok=False, provider="sms", error="Missing to/message")

    cfg = _vendor_provider_cfg(vendor, "sms")
    cfg_blob = (cfg.config if cfg else {}) or {}
    provider_override = str(cfg_blob.get("provider") or "").strip().lower() or None

    try:
        from sms_center.sms_service import send_google_sms, send_sms

        if provider_override == "google":
            res = send_google_sms(
                to,
                message,
                api_key=(str(cfg_blob.get("api_key") or "").strip() or None),
                sender_id=(str(cfg_blob.get("sender_id") or "").strip() or None),
                api_url=(str(cfg_blob.get("api_url") or "").strip() or None),
            )
            ok = bool(res.get("ok"))
            return SendResult(ok=ok, provider="sms/google", error=str(res) if not ok else "")

        res = send_sms(to, message, purpose="marketing", provider_override=provider_override)
        ok = bool(res.get("ok") or res.get("success"))
        return SendResult(ok=ok, provider=str(res.get("provider") or "sms"), error=str(res) if not ok else "")
    except Exception as exc:
        return SendResult(ok=False, provider="sms", error=f"{type(exc).__name__}: {exc}")


def send_vendor_email(*, vendor, to: str, subject: str, message: str) -> SendResult:
    to = (to or "").strip()
    subject = (subject or "").strip()[:160] or "Message"
    message = (message or "").strip()
    if not to or not message:
        return SendResult(ok=False, provider="email", error="Missing to/message")

    try:
        # Prefer Settings Center SMTP (runtime-editable by admin) if provided.
        smtp_host = str(_get_global_setting("smtp_host", "") or "").strip()
        smtp_port_raw = _get_global_setting("smtp_port", 587)
        try:
            smtp_port = int(smtp_port_raw or 587)
        except Exception:
            smtp_port = 587
        smtp_user = str(_get_global_setting("smtp_username", "") or "").strip()
        smtp_pass = str(_get_global_setting("smtp_password", "") or "").strip()
        smtp_tls = bool(_get_global_setting("smtp_use_tls", True))
        smtp_ssl = bool(_get_global_setting("smtp_use_ssl", False))
        default_from = str(_get_global_setting("smtp_from_email", "") or "").strip()

        cfg = _vendor_provider_cfg(vendor, "email")
        cfg_blob = (cfg.config if cfg else {}) or {}
        from_email = str(cfg_blob.get("from_email") or "").strip() or default_from or getattr(settings, "DEFAULT_FROM_EMAIL", "") or None

        if smtp_host:
            conn = get_connection(
                backend="django.core.mail.backends.smtp.EmailBackend",
                host=smtp_host,
                port=smtp_port,
                username=smtp_user or None,
                password=smtp_pass or None,
                use_tls=bool(smtp_tls) if not smtp_ssl else False,
                use_ssl=bool(smtp_ssl),
                fail_silently=False,
            )
            email = EmailMessage(subject=subject, body=message, from_email=from_email, to=[to], connection=conn)
            email.send(fail_silently=False)
        else:
            # Fallback to Django EMAIL_* settings (env-based).
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[to],
                fail_silently=False,
            )
        return SendResult(ok=True, provider="email")
    except Exception as exc:
        return SendResult(ok=False, provider="email", error=f"{type(exc).__name__}: {exc}")
