from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from commerce.models import Invoice, Payment
from core_settings.models import SettingDefinition, SettingValue
from khataapp.models import Party, ReminderLog
from khataapp.utils.whatsapp_utils import send_whatsapp_message
from smart_khata.services.credit_score import get_invoice_due_date, update_party_credit_metrics

logger = logging.getLogger(__name__)

DECIMAL_AGG_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _get_setting(user, key: str, default: Any):
    definition = SettingDefinition.objects.filter(key=key).first()
    if not definition:
        return default
    owner = user if definition.scope == "user" else None
    value_obj = SettingValue.objects.filter(definition=definition, owner=owner).first()
    if value_obj is None:
        return definition.default_value
    return value_obj.value


def reminders_enabled(user) -> bool:
    return bool(_get_setting(user, "khata_auto_reminders_enabled", True))


def reminder_offsets(user) -> List[int]:
    raw = _get_setting(user, "khata_reminder_offsets", [-3, 0, 3, 7])
    if isinstance(raw, list):
        out = []
        for x in raw:
            try:
                out.append(int(x))
            except Exception:
                continue
        return sorted(set(out))
    return [-3, 0, 3, 7]


def reminder_channels(user) -> List[str]:
    raw = _get_setting(user, "khata_reminder_channels", ["whatsapp"])
    if isinstance(raw, list):
        cleaned = []
        for x in raw:
            val = str(x or "").strip().lower()
            if val in {"whatsapp", "sms", "email"}:
                cleaned.append(val)
        return sorted(set(cleaned)) or ["whatsapp"]
    return ["whatsapp"]


def default_tone(user) -> str:
    val = str(_get_setting(user, "khata_default_tone", "professional") or "").strip().lower()
    return val if val in {"friendly", "professional", "strict"} else "professional"


def smart_timing_enabled(user) -> bool:
    return bool(_get_setting(user, "khata_smart_timing_enabled", True))


def risk_threshold(user) -> int:
    try:
        return int(_get_setting(user, "khata_risk_threshold", 40) or 40)
    except Exception:
        return 40


def template_for_tone(user, tone: str) -> str:
    key = {
        "friendly": "khata_template_friendly",
        "professional": "khata_template_professional",
        "strict": "khata_template_strict",
    }.get((tone or "").strip().lower(), "khata_template_professional")
    val = _get_setting(user, key, "")
    return str(val or "").strip()


def render_message(template: str, ctx: Dict[str, Any]) -> str:
    """
    Very small placeholder renderer:
      "Hello {{customer_name}}" -> replaces keys from ctx.
    """
    msg = str(template or "")
    for k, v in (ctx or {}).items():
        msg = msg.replace("{{" + str(k) + "}}", str(v))
    return msg.strip()


def _invoice_outstanding(invoice: Invoice) -> Decimal:
    paid = (
        Payment.objects.filter(invoice=invoice, is_deleted=False).aggregate(
            total=Coalesce(Sum("amount"), Value(0), output_field=DECIMAL_AGG_FIELD)
        )["total"]
        or Decimal("0.00")
    )
    amount = invoice.amount or Decimal("0.00")
    out = amount - paid
    return out if out > 0 else Decimal("0.00")


def _party_whatsapp(party: Party) -> str:
    return str((party.whatsapp_number or party.mobile or "")).strip().lstrip("+")


def _party_sms(party: Party) -> str:
    return str((party.sms_number or party.mobile or "")).strip().lstrip("+")


def _party_email(party: Party) -> str:
    return str((party.email or "")).strip()


def _already_sent_today(party: Party, invoice: Invoice, channel: str, offset: int, tone: str) -> bool:
    today = timezone.localdate()
    try:
        return ReminderLog.objects.filter(
            party=party,
            invoice=invoice,
            reminder_type="due",
            channel=channel,
            tone=tone,
            sent_at__date=today,
            payload__offset=int(offset),
        ).exists()
    except Exception:
        # JSON lookup may not be available on some DBs; fall back to a coarse check.
        return ReminderLog.objects.filter(
            party=party,
            invoice=invoice,
            reminder_type="due",
            channel=channel,
            tone=tone,
            sent_at__date=today,
        ).exists()


@dataclass(frozen=True)
class ReminderSendResult:
    ok: bool
    channel: str
    status: str
    detail: str


def _send_whatsapp(to: str, message: str) -> ReminderSendResult:
    if not to:
        return ReminderSendResult(ok=False, channel="whatsapp", status="missing_recipient", detail="No WhatsApp number")
    try:
        code, text = send_whatsapp_message(to, message)
        ok = 200 <= int(code or 0) < 300
        return ReminderSendResult(
            ok=ok,
            channel="whatsapp",
            status="sent" if ok else "failed",
            detail=f"{code}: {text[:400]}",
        )
    except Exception as exc:
        logger.exception("WhatsApp reminder send failed")
        return ReminderSendResult(ok=False, channel="whatsapp", status="exception", detail=str(exc))


def _send_sms(to: str, message: str) -> ReminderSendResult:
    if not to:
        return ReminderSendResult(ok=False, channel="sms", status="missing_recipient", detail="No SMS number")
    try:
        from sms_center.sms_service import send_google_sms

        res = send_google_sms(to, message)
        ok = bool(res.get("ok"))
        return ReminderSendResult(ok=ok, channel="sms", status="sent" if ok else "failed", detail=str(res)[:500])
    except Exception as exc:
        logger.exception("SMS reminder send failed")
        return ReminderSendResult(ok=False, channel="sms", status="exception", detail=str(exc))


def _send_email(to: str, subject: str, message: str) -> ReminderSendResult:
    if not to:
        return ReminderSendResult(ok=False, channel="email", status="missing_recipient", detail="No email address")
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or None
        send_mail(subject, message, from_email, [to], fail_silently=False)
        return ReminderSendResult(ok=True, channel="email", status="sent", detail="ok")
    except Exception as exc:
        logger.exception("Email reminder send failed")
        return ReminderSendResult(ok=False, channel="email", status="exception", detail=str(exc))


def _pick_tone_for_party(user, party: Party) -> str:
    tone = default_tone(user)
    thr = risk_threshold(user)
    try:
        if int(getattr(party, "credit_score", 0) or 0) < int(thr):
            tone = "strict"
    except Exception:
        pass
    return tone


def _dynamic_offset_for_party(user, party: Party, base_offsets: Iterable[int]) -> Optional[int]:
    if not smart_timing_enabled(user):
        return None
    try:
        avg_delay = int(getattr(party, "average_payment_delay", 0) or 0)
    except Exception:
        return None
    if avg_delay <= 1:
        return None
    dyn = max(0, avg_delay - 1)
    if dyn in set(int(x) for x in base_offsets):
        return None
    if dyn > 14:
        return None
    return int(dyn)


@transaction.atomic
def send_due_reminders_for_owner(
    owner,
    *,
    now_dt: Optional[datetime] = None,
    dry_run: bool = False,
    limit: int = 200,
) -> Dict[str, Any]:
    """
    Main automation entrypoint.

    Finds unpaid SALE invoices and sends reminders on configured offsets.
    """
    now_dt = now_dt or timezone.now()
    today = now_dt.date()

    if not reminders_enabled(owner):
        return {"ok": True, "status": "disabled", "sent": 0, "skipped": 0, "errors": 0}

    offsets = reminder_offsets(owner)
    channels = reminder_channels(owner)

    invoices = (
        Invoice.objects.select_related("order", "order__party")
        .filter(order__owner=owner, order__order_type__iexact="sale")
        .exclude(status__iexact="cancelled")
        .order_by("-created_at", "-id")
    )

    sent = 0
    skipped = 0
    errors = 0
    processed = 0

    for inv in invoices.iterator(chunk_size=200):
        if processed >= limit:
            break
        processed += 1

        try:
            # Skip fully paid invoices.
            if (inv.status or "").lower() == "paid":
                continue
        except Exception:
            pass

        order = getattr(inv, "order", None)
        party = getattr(order, "party", None)
        if not party or (party.party_type or "").lower() != "customer":
            continue

        # Keep Party metrics fresh so templates can use total_due/credit_score.
        try:
            update_party_credit_metrics(party)
        except Exception:
            pass

        due_dt = get_invoice_due_date(inv)
        delta_days = (today - due_dt).days  # -3 => 3 days before due date

        dyn = _dynamic_offset_for_party(owner, party, offsets)
        candidate_offsets = list(offsets)
        if dyn is not None:
            candidate_offsets.append(int(dyn))

        if delta_days not in set(int(x) for x in candidate_offsets):
            continue

        outstanding = _invoice_outstanding(inv)
        if outstanding <= 0:
            continue

        tone = _pick_tone_for_party(owner, party)
        tmpl = template_for_tone(owner, tone)
        if not tmpl:
            tmpl = template_for_tone(owner, "professional") or "Hello {{customer_name}}, payment pending."

        ctx = {
            "customer_name": party.name,
            "amount": f"{outstanding:.2f}",
            "total_due": f"{getattr(party, 'total_due', outstanding):.2f}",
            "days": str(max(delta_days, 0)),
            "due_in_days": str(abs(delta_days)) if delta_days < 0 else "0",
            "invoice_number": getattr(inv, "number", "") or str(inv.id),
            "due_date": due_dt.strftime("%Y-%m-%d"),
            "pay_link": getattr(inv, "payment_link", "") or "",
        }
        message = render_message(tmpl, ctx)

        for channel in channels:
            if _already_sent_today(party, inv, channel, delta_days, tone):
                skipped += 1
                continue

            payload = {
                "offset": int(delta_days),
                "due_date": ctx["due_date"],
                "invoice_id": int(inv.id),
                "invoice_number": ctx["invoice_number"],
                "outstanding": str(outstanding),
            }

            if dry_run:
                ReminderLog.objects.create(
                    party=party,
                    invoice=inv,
                    reminder_type="due",
                    tone=tone,
                    channel=channel,
                    status="scheduled",
                    scheduled_for=now_dt,
                    payload={**payload, "dry_run": True, "preview": message[:500]},
                )
                skipped += 1
                continue

            if channel == "whatsapp":
                res = _send_whatsapp(_party_whatsapp(party), message)
            elif channel == "sms":
                res = _send_sms(_party_sms(party), message)
            else:
                subject = f"Payment Reminder - {ctx['invoice_number']}"
                res = _send_email(_party_email(party), subject, message)

            status = "sent" if res.ok else "failed"
            if res.ok:
                sent += 1
            else:
                errors += 1

            ReminderLog.objects.create(
                party=party,
                invoice=inv,
                reminder_type="due",
                tone=tone,
                channel=channel,
                status=status,
                scheduled_for=now_dt,
                sent_at=now_dt if res.ok else None,
                payload={**payload, "detail": res.detail, "message": message[:800]},
            )

    return {"ok": errors == 0, "status": "ok", "sent": sent, "skipped": skipped, "errors": errors}


@transaction.atomic
def send_reminder_for_invoice(
    owner,
    invoice: Invoice,
    *,
    channels: Optional[List[str]] = None,
    tone: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Manual "send now" helper used by API/UI.
    """
    now_dt = timezone.now()
    today = now_dt.date()

    order = getattr(invoice, "order", None)
    party = getattr(order, "party", None)
    if not party or (party.party_type or "").lower() != "customer":
        return {"ok": False, "status": "invalid_party"}

    if getattr(order, "owner_id", None) != getattr(owner, "id", None):
        return {"ok": False, "status": "forbidden"}

    try:
        if (invoice.status or "").lower() in {"paid", "cancelled"}:
            return {"ok": True, "status": "already_settled"}
    except Exception:
        pass

    try:
        update_party_credit_metrics(party)
    except Exception:
        pass

    due_dt = get_invoice_due_date(invoice)
    delta_days = (today - due_dt).days

    outstanding = _invoice_outstanding(invoice)
    if outstanding <= 0:
        return {"ok": True, "status": "no_outstanding"}

    if channels is None:
        channels = reminder_channels(owner)
    else:
        channels = [str(c or "").strip().lower() for c in channels]
        channels = [c for c in channels if c in {"whatsapp", "sms", "email"}] or reminder_channels(owner)
    tone = (tone or _pick_tone_for_party(owner, party)).strip().lower()
    if tone not in {"friendly", "professional", "strict"}:
        tone = default_tone(owner)

    tmpl = template_for_tone(owner, tone) or template_for_tone(owner, "professional")
    ctx = {
        "customer_name": party.name,
        "amount": f"{outstanding:.2f}",
        "total_due": f"{getattr(party, 'total_due', outstanding):.2f}",
        "days": str(max(delta_days, 0)),
        "due_in_days": str(abs(delta_days)) if delta_days < 0 else "0",
        "invoice_number": getattr(invoice, "number", "") or str(invoice.id),
        "due_date": due_dt.strftime("%Y-%m-%d"),
        "pay_link": getattr(invoice, "payment_link", "") or "",
    }
    message = render_message(tmpl or "", ctx) or "Payment reminder"

    sent = 0
    failed = 0
    results = []

    for channel in channels:
        payload = {
            "offset": int(delta_days),
            "due_date": ctx["due_date"],
            "invoice_id": int(invoice.id),
            "invoice_number": ctx["invoice_number"],
            "outstanding": str(outstanding),
            "manual": True,
        }
        if dry_run:
            ReminderLog.objects.create(
                party=party,
                invoice=invoice,
                reminder_type="due",
                tone=tone,
                channel=channel,
                status="scheduled",
                scheduled_for=now_dt,
                payload={**payload, "dry_run": True, "preview": message[:500]},
            )
            results.append({"channel": channel, "status": "scheduled"})
            continue

        if channel == "whatsapp":
            res = _send_whatsapp(_party_whatsapp(party), message)
        elif channel == "sms":
            res = _send_sms(_party_sms(party), message)
        else:
            subject = f"Payment Reminder - {ctx['invoice_number']}"
            res = _send_email(_party_email(party), subject, message)

        status = "sent" if res.ok else "failed"
        if res.ok:
            sent += 1
        else:
            failed += 1

        ReminderLog.objects.create(
            party=party,
            invoice=invoice,
            reminder_type="due",
            tone=tone,
            channel=channel,
            status=status,
            scheduled_for=now_dt,
            sent_at=now_dt if res.ok else None,
            payload={**payload, "detail": res.detail, "message": message[:800]},
        )
        results.append({"channel": channel, "status": status, "detail": res.detail})

    return {"ok": failed == 0, "status": "ok", "sent": sent, "failed": failed, "results": results}
