from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable, Optional

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from khatapro import DISABLE_CELERY
from khataapp.models import Party
from whatsapp.models import Customer, WhatsAppAccount, WhatsAppMessage
from whatsapp.providers.meta_cloud import verify_meta_signature
from whatsapp.tasks import process_inbound_message

logger = logging.getLogger(__name__)

_DIGITS = re.compile(r"[^0-9]")


def _digits(s: str) -> str:
    return _DIGITS.sub("", s or "")


def _extract_meta_messages(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    entries = payload.get("entry") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []

    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value") if isinstance(change.get("value"), dict) else {}
            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
            phone_number_id = str(metadata.get("phone_number_id") or "").strip()
            display_phone_number = str(metadata.get("display_phone_number") or "").strip()

            contact_name = ""
            contacts = value.get("contacts")
            if isinstance(contacts, list) and contacts:
                c0 = contacts[0] if isinstance(contacts[0], dict) else {}
                profile = c0.get("profile") if isinstance(c0.get("profile"), dict) else {}
                contact_name = str(profile.get("name") or "").strip()

            messages = value.get("messages")
            if not isinstance(messages, list):
                continue
            for m in messages:
                if not isinstance(m, dict):
                    continue
                msg_type = str(m.get("type") or "").strip().lower()
                from_number = str(m.get("from") or "").strip()
                message_id = str(m.get("id") or "").strip()

                text = ""
                if msg_type == "text":
                    text = str((m.get("text") or {}).get("body") or "").strip()
                elif msg_type == "button":
                    text = str((m.get("button") or {}).get("text") or "").strip()
                elif msg_type == "interactive":
                    inter = m.get("interactive") if isinstance(m.get("interactive"), dict) else {}
                    br = inter.get("button_reply") if isinstance(inter.get("button_reply"), dict) else {}
                    lr = inter.get("list_reply") if isinstance(inter.get("list_reply"), dict) else {}
                    text = str(br.get("title") or br.get("id") or lr.get("title") or lr.get("id") or "").strip()
                elif msg_type == "location":
                    # Keep a simple marker so the bot engine can react, but persist full payload in raw.
                    text = "location"

                out.append(
                    {
                        "phone_number_id": phone_number_id,
                        "display_phone_number": display_phone_number,
                        "from_number": from_number,
                        "message_id": message_id,
                        "message_type": msg_type,
                        "text": text,
                        "contact_name": contact_name,
                        "raw": m,
                    }
                )
    return out


def _enqueue_process(message_log_id: int) -> None:
    if DISABLE_CELERY:
        try:
            process_inbound_message.run(message_log_id)  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Synchronous inbound processing failed")
        return
    try:
        # Avoid blocking webhooks when broker is down; fall back to sync.
        process_inbound_message.apply_async(args=(message_log_id,), retry=False, ignore_result=True)
    except Exception:
        # Celery not running; process synchronously (dev-friendly).
        try:
            process_inbound_message.run(message_log_id)  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Synchronous inbound processing failed")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_meta_webhook(request, account_id: str):
    """
    WhatsApp Cloud API webhook (Meta official).

    - GET: verification challenge (hub.*)
    - POST: inbound messages -> queued bot processing
    """
    account = WhatsAppAccount.objects.filter(id=account_id, provider=WhatsAppAccount.Provider.META_CLOUD_API).select_related("owner").first()
    if not account:
        return HttpResponse("not_found", status=404)

    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token and token == (account.meta_verify_token or ""):
            return HttpResponse(challenge or "", status=200)
        return HttpResponse("forbidden", status=403)

    raw_body = request.body or b""
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return HttpResponse("bad_request", status=400)

    # Optional signature verification (recommended).
    app_secret = (account.meta_app_secret or "").strip()
    provided_sig = request.headers.get("X-Hub-Signature-256")
    if app_secret:
        if not verify_meta_signature(app_secret=app_secret, payload_bytes=raw_body, provided_signature=provided_sig):
            return HttpResponse("invalid_signature", status=403)

    # Extract messages and queue.
    msgs = list(_extract_meta_messages(payload))
    if not msgs:
        # Status updates or other non-message events.
        return HttpResponse("EVENT_RECEIVED", status=200)

    for m in msgs:
        phone_number_id = str(m.get("phone_number_id") or "").strip()
        if account.meta_phone_number_id and phone_number_id and account.meta_phone_number_id != phone_number_id:
            # Mismatch: do not process under this tenant.
            continue

        from_number = str(m.get("from_number") or "").strip()
        text = str(m.get("text") or "").strip()
        message_id = str(m.get("message_id") or "").strip()
        msg_type = str(m.get("message_type") or "").strip().lower()
        contact_name = str(m.get("contact_name") or "").strip()

        if not from_number:
            continue

        # Deduplicate by provider message id when available.
        if message_id and WhatsAppMessage.objects.filter(whatsapp_account=account, provider_message_id=message_id, direction=WhatsAppMessage.Direction.INBOUND).exists():
            continue

        party = None
        try:
            d = _digits(from_number)
            d10 = d[-10:] if len(d) > 10 else d
            if d10:
                party = Party.objects.filter(owner=account.owner).filter(Q(whatsapp_number__endswith=d10) | Q(mobile__endswith=d10)).order_by("-id").first()
        except Exception:
            party = None

        customer, created = Customer.objects.get_or_create(
            owner=account.owner,
            whatsapp_account=account,
            phone_number=from_number,
            defaults={"display_name": contact_name, "party": party},
        )
        if (not created) and contact_name and not (customer.display_name or "").strip():
            customer.display_name = contact_name
            customer.save(update_fields=["display_name", "updated_at"])
        try:
            customer.touch_seen()
        except Exception:
            pass

        log = WhatsAppMessage.objects.create(
            owner=account.owner,
            whatsapp_account=account,
            customer=customer,
            direction=WhatsAppMessage.Direction.INBOUND,
            from_number=from_number,
            to_number=(account.phone_number or str(m.get("display_phone_number") or "")).strip(),
            body=text,
            message_type=msg_type,
            provider_message_id=message_id,
            raw_payload={"meta": m.get("raw") or {}, "received_at": timezone.now().isoformat()},
            status=WhatsAppMessage.Status.RECEIVED,
        )
        _enqueue_process(int(log.id))

    return HttpResponse("EVENT_RECEIVED", status=200)


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_gateway_inbound_webhook(request, account_id: str):
    """
    Generic inbound webhook for QR/Web gateways.

    Expected JSON (flexible keys):
    { "from": "...", "to": "...", "body": "...", "message_id": "...", "type": "text" }

    Security:
    - Header X-WA-Secret or query ?secret must match account.webhook_secret.
    """
    account = WhatsAppAccount.objects.filter(id=account_id, provider=WhatsAppAccount.Provider.WEB_GATEWAY).select_related("owner").first()
    if not account:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    provided = (request.headers.get("X-WA-Secret") or request.GET.get("secret") or "").strip()
    if not provided or provided != (account.webhook_secret or ""):
        return JsonResponse({"ok": False, "error": "invalid_secret"}, status=403)

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)
    payload = payload if isinstance(payload, dict) else {}

    from_number = str(payload.get("from") or payload.get("mobile") or payload.get("sender") or "").strip()
    to_number = str(payload.get("to") or payload.get("receiver") or "").strip()
    body = str(payload.get("body") or payload.get("message") or payload.get("text") or "").strip()
    caption = str(payload.get("caption") or "").strip()
    msg_type = str(payload.get("type") or payload.get("message_type") or "").strip().lower()
    message_id = str(payload.get("message_id") or payload.get("id") or payload.get("external_id") or "").strip()[:120]

    if msg_type == "location" and not body:
        body = "location"
    if not body and caption and msg_type in {"image", "document", "video"}:
        body = caption

    if not from_number:
        return JsonResponse({"ok": False, "error": "missing_from"}, status=400)

    if message_id and WhatsAppMessage.objects.filter(whatsapp_account=account, provider_message_id=message_id, direction=WhatsAppMessage.Direction.INBOUND).exists():
        return JsonResponse({"ok": True, "status": "duplicate_ignored"})

    party = None
    try:
        d = _digits(from_number)
        d10 = d[-10:] if len(d) > 10 else d
        if d10:
            party = Party.objects.filter(owner=account.owner).filter(Q(whatsapp_number__endswith=d10) | Q(mobile__endswith=d10)).order_by("-id").first()
    except Exception:
        party = None

    customer, _ = Customer.objects.get_or_create(
        owner=account.owner,
        whatsapp_account=account,
        phone_number=from_number,
        defaults={"display_name": str(payload.get("name") or "").strip(), "party": party},
    )
    try:
        customer.touch_seen()
    except Exception:
        pass

    log = WhatsAppMessage.objects.create(
        owner=account.owner,
        whatsapp_account=account,
        customer=customer,
        direction=WhatsAppMessage.Direction.INBOUND,
        from_number=from_number,
        to_number=(to_number or account.phone_number or "").strip(),
        body=body,
        message_type=msg_type or "text",
        provider_message_id=message_id,
        raw_payload=payload,
        status=WhatsAppMessage.Status.RECEIVED,
    )
    _enqueue_process(int(log.id))
    return JsonResponse({"ok": True, "queued": True, "message_log_id": log.id})
