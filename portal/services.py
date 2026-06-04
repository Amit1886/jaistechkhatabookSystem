from __future__ import annotations

import logging
import re
import secrets
import string
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry
from portal.models import PortalPermission, PortalUser, WelcomeMessageLog
from whatsapp.api_connector import send_whatsapp_message

logger = logging.getLogger(__name__)


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


def portal_enabled() -> bool:
    return bool(_get_global_setting("portal_enabled", True))


def customer_portal_enabled() -> bool:
    return bool(_get_global_setting("portal_customer_enabled", True))


def supplier_portal_enabled() -> bool:
    return bool(_get_global_setting("portal_supplier_enabled", True))


def customer_split_dashboards_enabled() -> bool:
    return bool(_get_global_setting("portal_customer_split_dashboards", True))


def supplier_split_dashboards_enabled() -> bool:
    return bool(_get_global_setting("portal_supplier_split_dashboards", True))


def portal_base_url() -> str:
    val = str(_get_global_setting("portal_base_url", "") or "").strip()
    if val:
        return val.rstrip("/")
    return (getattr(settings, "BASE_URL", "http://localhost:8000") or "http://localhost:8000").rstrip("/")


def _role_for_party_type(party_type: str) -> str:
    pt = (party_type or "").strip().lower()
    if pt == "supplier":
        return PortalUser.Role.SUPPLIER
    return PortalUser.Role.CUSTOMER


def _sanitize_username_base(value: str) -> str:
    value = (value or "").strip().lower()
    # Keep alnum + dot/underscore
    value = re.sub(r"[^a-z0-9._]+", "", value)
    value = value.strip("._")
    return value or "party"


def generate_username(*, party_name: str, mobile: str = "") -> str:
    base = _sanitize_username_base(party_name)
    digits = re.sub(r"[^0-9]", "", mobile or "")
    suffix = digits[-4:] if len(digits) >= 4 else secrets.randbelow(10_000)

    # Keep it short and readable.
    base = base[:20]
    candidate = f"{base}{suffix}"

    if not PortalUser.objects.filter(username=candidate).exists():
        return candidate

    for _ in range(30):
        extra = secrets.randbelow(10_000)
        cand = f"{base}{suffix}{extra}"
        cand = cand[:80]
        if not PortalUser.objects.filter(username=cand).exists():
            return cand

    # Fallback
    return f"{base}{secrets.token_hex(4)}"[:80]


def generate_password(length: int = 12) -> str:
    length = max(int(length or 12), 10)
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


DEFAULT_PERMISSION_KEYS = {
    PortalUser.Role.CUSTOMER: [
        "view_invoices",
        "view_reports",
        "place_orders",
        "make_payments",
    ],
    PortalUser.Role.SUPPLIER: [
        "view_invoices",
        "view_reports",
        "view_purchase_history",
        "view_demand_trends",
    ],
}


def ensure_default_permissions(portal_user: PortalUser) -> None:
    keys = DEFAULT_PERMISSION_KEYS.get(portal_user.role, [])
    for k in keys:
        PortalPermission.objects.get_or_create(portal_user=portal_user, key=k, defaults={"allowed": True})


def _redact_password(message: str, password: str) -> str:
    if not password:
        return message
    return (message or "").replace(password, "******")


@dataclass(frozen=True)
class WelcomeSendResult:
    ok: bool
    channel: str
    status: str
    to: str = ""
    response: str = ""


def send_welcome_kit(*, portal_user: PortalUser, plain_password: str, login_link: str) -> list[WelcomeSendResult]:
    """
    Best-effort sends a welcome kit over WhatsApp/SMS/Email based on admin settings.
    Always logs each attempt to WelcomeMessageLog.
    """
    party = portal_user.party

    msg = (
        "Welcome to the Business Portal.\n\n"
        f"Login ID: {portal_user.username}\n"
        f"Password: {plain_password}\n\n"
        f"Login here:\n{login_link}\n\n"
        "From your portal you can:\n"
        "- View invoices\n"
        "- Download reports\n"
        "- Check outstanding balance\n"
        "- Make payments\n"
        "- Place orders\n"
    )

    redacted = _redact_password(msg, plain_password)

    send_wa = bool(_get_global_setting("portal_welcome_whatsapp", True))
    send_sms = bool(_get_global_setting("portal_welcome_sms", True))
    send_email = bool(_get_global_setting("portal_welcome_email", True))

    results: list[WelcomeSendResult] = []

    def _log(channel: str, status: str, to: str, response: str = ""):
        try:
            WelcomeMessageLog.objects.create(
                owner=portal_user.owner,
                party=party,
                portal_user=portal_user,
                channel=channel,
                status=status,
                to=to or "",
                message_preview=redacted[:1800],
                payload={"login_link": login_link, "username": portal_user.username},
                response=(response or "")[:3000],
            )
        except Exception:
            logger.exception("Failed to log welcome message")

    # WhatsApp
    to_wa = (getattr(party, "whatsapp_number", "") or getattr(party, "mobile", "") or "").strip().lstrip("+")
    if send_wa and to_wa:
        try:
            r = send_whatsapp_message(to=to_wa, message=msg)
            status = WelcomeMessageLog.Status.SENT if r.ok else WelcomeMessageLog.Status.FAILED
            _log(WelcomeMessageLog.Channel.WHATSAPP, status, to_wa, response=r.response_text)
            results.append(WelcomeSendResult(ok=bool(r.ok), channel="whatsapp", status=status, to=to_wa, response=r.response_text))
        except Exception as exc:
            _log(WelcomeMessageLog.Channel.WHATSAPP, WelcomeMessageLog.Status.FAILED, to_wa, response=str(exc))
            results.append(WelcomeSendResult(ok=False, channel="whatsapp", status=WelcomeMessageLog.Status.FAILED, to=to_wa, response=str(exc)))
    else:
        _log(WelcomeMessageLog.Channel.WHATSAPP, WelcomeMessageLog.Status.SKIPPED, to_wa, response="Disabled or missing WhatsApp number")
        results.append(WelcomeSendResult(ok=False, channel="whatsapp", status=WelcomeMessageLog.Status.SKIPPED, to=to_wa, response="skipped"))

    # SMS (via sms_center Google gateway if configured)
    to_sms = (getattr(party, "sms_number", "") or getattr(party, "mobile", "") or "").strip().lstrip("+")
    if send_sms and to_sms:
        try:
            from sms_center.sms_service import send_google_sms

            resp = send_google_sms(mobile=to_sms, text_message=msg)
            ok = bool(resp.get("ok"))
            status = WelcomeMessageLog.Status.SENT if ok else WelcomeMessageLog.Status.FAILED
            _log(WelcomeMessageLog.Channel.SMS, status, to_sms, response=str(resp))
            results.append(WelcomeSendResult(ok=ok, channel="sms", status=status, to=to_sms, response=str(resp)))
        except Exception as exc:
            _log(WelcomeMessageLog.Channel.SMS, WelcomeMessageLog.Status.FAILED, to_sms, response=str(exc))
            results.append(WelcomeSendResult(ok=False, channel="sms", status=WelcomeMessageLog.Status.FAILED, to=to_sms, response=str(exc)))
    else:
        _log(WelcomeMessageLog.Channel.SMS, WelcomeMessageLog.Status.SKIPPED, to_sms, response="Disabled or missing mobile")
        results.append(WelcomeSendResult(ok=False, channel="sms", status=WelcomeMessageLog.Status.SKIPPED, to=to_sms, response="skipped"))

    # Email
    to_email = (getattr(party, "email", "") or "").strip()
    if send_email and to_email:
        try:
            subject = "Welcome to Business Portal"
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
            send_mail(subject, msg, from_email, [to_email], fail_silently=True)
            _log(WelcomeMessageLog.Channel.EMAIL, WelcomeMessageLog.Status.SENT, to_email, response="sent (fail_silently)")
            results.append(WelcomeSendResult(ok=True, channel="email", status=WelcomeMessageLog.Status.SENT, to=to_email, response="sent"))
        except Exception as exc:
            _log(WelcomeMessageLog.Channel.EMAIL, WelcomeMessageLog.Status.FAILED, to_email, response=str(exc))
            results.append(WelcomeSendResult(ok=False, channel="email", status=WelcomeMessageLog.Status.FAILED, to=to_email, response=str(exc)))
    else:
        _log(WelcomeMessageLog.Channel.EMAIL, WelcomeMessageLog.Status.SKIPPED, to_email, response="Disabled or missing email")
        results.append(WelcomeSendResult(ok=False, channel="email", status=WelcomeMessageLog.Status.SKIPPED, to=to_email, response="skipped"))

    return results


@dataclass(frozen=True)
class PortalAccountCreateResult:
    portal_user: PortalUser
    created: bool
    plain_password: str = ""


def create_portal_account_for_party(party, *, created_by=None, rotate_password: bool = False) -> PortalAccountCreateResult | None:
    """
    Ensures a PortalUser exists for this Party.

    If rotate_password=True, a new password is generated and sent (best-effort).
    """
    if not party or not getattr(party, "id", None):
        return None
    owner = getattr(party, "owner", None)
    if not owner:
        return None
    if not portal_enabled():
        return None

    role = _role_for_party_type(getattr(party, "party_type", ""))
    if role == PortalUser.Role.CUSTOMER and not customer_portal_enabled():
        return None
    if role == PortalUser.Role.SUPPLIER and not supplier_portal_enabled():
        return None

    with transaction.atomic():
        pu = PortalUser.objects.select_for_update().filter(party=party).first()
        created = False
        plain_password = ""
        if not pu:
            username = generate_username(party_name=getattr(party, "name", ""), mobile=getattr(party, "mobile", ""))
            plain_password = generate_password(12)
            pu = PortalUser(
                owner=owner,
                party=party,
                role=role,
                username=username,
                is_active=True,
                must_change_password=True,
                created_by=created_by if getattr(created_by, "id", None) else None,
            )
            pu.set_password(plain_password)
            pu.save()
            created = True
        elif rotate_password:
            plain_password = generate_password(12)
            pu.set_password(plain_password)
            pu.must_change_password = True
            pu.save(update_fields=["password_hash", "must_change_password"])

        # Keep owner/role synced if party changed.
        needs_update = False
        if pu.owner_id != getattr(owner, "id", None):
            pu.owner = owner
            needs_update = True
        if pu.role != role:
            pu.role = role
            needs_update = True
        if needs_update:
            pu.save(update_fields=["owner", "role"])

        ensure_default_permissions(pu)

    # Send welcome kit only on creation or password rotation.
    if plain_password:
        link = f"{portal_base_url()}/accounts/login/?role={pu.role}"
        def _send():
            try:
                send_welcome_kit(portal_user=pu, plain_password=plain_password, login_link=link)
            except Exception:
                logger.exception("Welcome kit send failed for portal_user=%s", getattr(pu, "id", None))

        try:
            transaction.on_commit(_send)
        except Exception:
            _send()

    return PortalAccountCreateResult(portal_user=pu, created=created, plain_password=plain_password)
