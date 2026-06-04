from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

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


def _digits_only(value: str) -> str:
    return "".join([c for c in (value or "") if c.isdigit()]).strip()


def _base_url() -> str:
    """
    Returns something like: https://example.com
    If empty, caller can still use relative URLs.
    """
    base = str(_get_global_setting("public_base_url", "") or "").strip()
    if base:
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"https://{base}"
        return base.rstrip("/")

    try:
        from django.contrib.sites.models import Site

        domain = (Site.objects.get_current().domain or "").strip()
        if domain:
            if not domain.startswith("http://") and not domain.startswith("https://"):
                domain = f"https://{domain}"
            return domain.rstrip("/")
    except Exception:
        pass

    return ""


def _already_has_login_link(text: str) -> bool:
    t = (text or "").lower()
    if ("/accounts/login-link/" in t) or ("login-link/" in t):
        return True
    # Also treat explicit login URLs as already containing a login link.
    if "/accounts/login/" in t or "/accounts/login?" in t:
        return True
    if "login here:" in t or "login:" in t:
        return True
    return False


def _resolve_user_for_recipient(recipient: str):
    """
    Tries to resolve a customer/party user based on recipient phone digits.
    Returns (user, party) where party may be None.
    """
    digits = _digits_only(recipient)
    if not digits:
        return None, None
    last10 = digits[-10:] if len(digits) >= 10 else digits

    User = get_user_model()
    user = None
    party = None

    try:
        user = User.objects.filter(mobile__endswith=last10).first()
    except Exception:
        user = None

    try:
        from khataapp.models import Party

        party = (
            Party.objects.filter(mobile__endswith=last10).first()
            or Party.objects.filter(whatsapp_number__endswith=last10).first()
        )
    except Exception:
        party = None

    # For party-only records, ensure a user exists (same logic as khataapp.models auto_create_login_link)
    if party and not user:
        try:
            safe_email = f"{(party.mobile or last10)}@party.local"
        except Exception:
            safe_email = f"{last10}@party.local"
        try:
            user = User.objects.filter(email__iexact=safe_email).first()
        except Exception:
            user = None
        if not user:
            try:
                user = User.objects.create(
                    username=(getattr(party, "name", "") or "Party")[:150],
                    email=safe_email,
                    mobile=getattr(party, "mobile", "") or last10,
                    is_active=False,
                    is_otp_verified=False,
                )
            except Exception:
                user = None

    return user, party


def _ensure_dashboard_login_link(user):
    """
    Returns active, non-expired dashboard LoginLink for this user.
    """
    if not user:
        return None
    try:
        from khataapp.models import LoginLink

        now = timezone.now()
        link = (
            LoginLink.objects.filter(user=user, purpose="dashboard", is_active=True, expires_at__gte=now)
            .order_by("-expires_at", "-id")
            .first()
        )
        if link:
            return link

        try:
            expires_hours = int(_get_global_setting("customer_login_link_expires_hours", 168) or 168)
        except Exception:
            expires_hours = 168
        if expires_hours <= 0:
            expires_hours = 168

        # Deactivate older active links to keep DB tidy.
        try:
            LoginLink.objects.filter(user=user, purpose="dashboard", is_active=True).update(is_active=False)
        except Exception:
            pass

        return LoginLink.objects.create(
            user=user,
            purpose="dashboard",
            expires_at=now + timedelta(hours=expires_hours),
            is_active=True,
        )
    except Exception:
        logger.exception("Failed to ensure LoginLink")
        return None


def build_customer_login_url_for_recipient(recipient: str) -> str:
    """
    recipient: phone digits (with/without country code).
    """
    user, _party = _resolve_user_for_recipient(recipient)
    link = _ensure_dashboard_login_link(user)
    if not link:
        base = _base_url()
        path = reverse("accounts:login")
        return f"{base}{path}" if base else path

    base = _base_url()
    path = reverse("accounts:login_link", args=[str(link.token)])
    return f"{base}{path}" if base else path


def maybe_append_customer_login_link(*, channel: str, recipient: str, message: str, purpose: str = "generic") -> str:
    """
    Appends a customer login-link to message text if enabled via Settings Center.

    channel: sms|whatsapp|email|notification
    purpose: otp|generic|...
    """
    channel = (channel or "").strip().lower()
    purpose = (purpose or "generic").strip().lower()
    message = str(message or "").strip()
    if not message:
        return message

    if not _bool_setting("customer_login_link_enabled", True):
        return message

    if _already_has_login_link(message):
        return message

    if purpose == "otp" and not _bool_setting("customer_login_link_append_to_otp", False):
        return message

    channel_flag_key = {
        "sms": "customer_login_link_append_to_sms",
        "whatsapp": "customer_login_link_append_to_whatsapp",
        "email": "customer_login_link_append_to_email",
        "notification": "customer_login_link_append_to_notifications",
    }.get(channel, "")
    if channel_flag_key and not _bool_setting(channel_flag_key, True):
        return message

    url = build_customer_login_url_for_recipient(recipient)
    if not url:
        return message

    template = str(_get_global_setting("customer_login_link_footer_template", "\n\nLogin: {url}") or "\n\nLogin: {url}")
    try:
        footer = template.format(url=url)
    except Exception:
        footer = f"\n\nLogin: {url}"

    return f"{message}{footer}"
