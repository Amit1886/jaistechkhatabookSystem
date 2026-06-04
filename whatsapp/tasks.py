from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Optional

from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from khataapp.models import Party
from whatsapp.models import BroadcastCampaign, Customer, WhatsAppAccount, WhatsAppMessage
from whatsapp.services.message_router import route_inbound_message
from whatsapp.services.provider_clients import healthcheck, send_document_link, send_image_link, send_text
from whatsapp.services.supplier_reminders import send_supplier_payment_reminders

logger = logging.getLogger(__name__)

_DIGITS = re.compile(r"[^0-9]")


def _digits(s: str) -> str:
    return _DIGITS.sub("", s or "")


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _extract_location(raw_payload: dict) -> tuple[Optional[Decimal], Optional[Decimal]]:
    raw_payload = raw_payload if isinstance(raw_payload, dict) else {}
    meta = raw_payload.get("meta") if isinstance(raw_payload.get("meta"), dict) else {}
    loc = None
    for candidate in (meta.get("location"), raw_payload.get("location"), raw_payload.get("loc")):
        if isinstance(candidate, dict):
            loc = candidate
            break
    if not loc:
        return None, None

    lat = loc.get("latitude", loc.get("lat"))
    lng = loc.get("longitude", loc.get("lng", loc.get("long")))
    return _to_decimal(lat), _to_decimal(lng)


def _resolve_party_for_customer(*, owner, phone_number: str) -> Optional[Party]:
    d = _digits(phone_number)
    d10 = d[-10:] if len(d) > 10 else d
    if not d10:
        return None
    # Prefer exact matches first
    p = Party.objects.filter(owner=owner).filter(Q(whatsapp_number__endswith=d10) | Q(mobile__endswith=d10)).order_by("-id").first()
    return p


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True)
def process_inbound_message(self, message_log_id: int) -> dict:
    msg = (
        WhatsAppMessage.objects.select_related("owner", "whatsapp_account", "customer")
        .filter(id=message_log_id)
        .first()
    )
    if not msg:
        return {"ok": False, "error": "message_not_found"}

    if msg.status in {WhatsAppMessage.Status.PROCESSED, WhatsAppMessage.Status.IGNORED}:
        return {"ok": True, "status": msg.status}

    account: Optional[WhatsAppAccount] = msg.whatsapp_account
    if not account:
        msg.status = WhatsAppMessage.Status.IGNORED
        msg.error = "missing_whatsapp_account"
        msg.save(update_fields=["status", "error"])
        return {"ok": False, "error": msg.error}

    owner = msg.owner

    customer = msg.customer
    if not customer:
        party = _resolve_party_for_customer(owner=owner, phone_number=msg.from_number)
        customer, _ = Customer.objects.get_or_create(
            owner=owner,
            whatsapp_account=account,
            phone_number=(msg.from_number or "").strip(),
            defaults={"display_name": "", "party": party},
        )
        msg.customer = customer
        msg.save(update_fields=["customer"])

    try:
        customer.touch_seen()
    except Exception:
        pass
    try:
        account.touch_seen()
    except Exception:
        pass

    # Store last known location (if message contains it).
    try:
        if (msg.message_type or "").lower() == "location":
            lat, lng = _extract_location(msg.raw_payload or {})
            if lat is not None and lng is not None:
                customer.last_location_lat = lat
                customer.last_location_lng = lng
                customer.last_location_at = timezone.now()
                customer.save(update_fields=["last_location_lat", "last_location_lng", "last_location_at", "updated_at"])
    except Exception:
        pass

    # Basic spam/rate protection (per account + sender). Tune via env or cache backend.
    key = f"wa:in:{account.id}:{_digits(msg.from_number)}:{int(timezone.now().timestamp() // 10)}"
    try:
        hits = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=20)
        hits = 1
    if hits > 20:
        msg.status = WhatsAppMessage.Status.IGNORED
        msg.error = "rate_limited"
        msg.save(update_fields=["status", "error"])
        return {"ok": False, "error": "rate_limited"}

    # Media-aware automation (voice notes, supplier invoice photos, etc.)
    try:
        from whatsapp.services.inbound_media import handle_inbound_media_message

        media_res = handle_inbound_media_message(owner=owner, account=account, customer=customer, msg=msg)
        if media_res is not None:
            engine_res = media_res
        else:
            # Voice transcription may have updated msg.body; use the latest value.
            engine_res = route_inbound_message(owner=owner, account=account, customer=customer, inbound_text=msg.body or "")
    except Exception:
        engine_res = route_inbound_message(owner=owner, account=account, customer=customer, inbound_text=msg.body or "")
    if not (engine_res.reply or engine_res.attachments or engine_res.invoice_pdf_url):
        msg.status = WhatsAppMessage.Status.IGNORED
        msg.error = engine_res.intent or "no_reply"
        msg.save(update_fields=["status", "error"])
        return {"ok": True, "status": msg.status}

    outbound_results = []

    if engine_res.reply:
        outbound = send_text(account=account, to=msg.from_number, text=engine_res.reply)
        outbound_results.append(outbound)
        WhatsAppMessage.objects.create(
            owner=owner,
            whatsapp_account=account,
            customer=customer,
            direction=WhatsAppMessage.Direction.OUTBOUND,
            from_number=(account.phone_number or msg.to_number or "").strip(),
            to_number=(msg.from_number or "").strip(),
            body=engine_res.reply,
            message_type="text",
            provider_message_id=outbound.provider_message_id,
            raw_payload={"provider": outbound.provider, "status_code": outbound.status_code, "response": outbound.response_text[:5000]},
            status=WhatsAppMessage.Status.PROCESSED if outbound.ok else WhatsAppMessage.Status.FAILED,
            error="" if outbound.ok else (outbound.response_text or "")[:2000],
            parsed_intent=engine_res.intent or "",
            parsed_payload={
                "order_id": engine_res.order_id,
                "invoice_id": engine_res.invoice_id,
                "payment_url": engine_res.payment_url,
                "invoice_pdf_url": engine_res.invoice_pdf_url,
            },
            reference_type="commerce.Order" if engine_res.order_id else "",
            reference_id=engine_res.order_id,
        )

    # Media attachments from no-code bot flows.
    for att in (engine_res.attachments or ()):
        if not isinstance(att, dict):
            continue
        typ = str(att.get("type") or "").strip().lower()
        link = str(att.get("link") or "").strip()
        caption = str(att.get("caption") or "").strip()
        filename = str(att.get("filename") or "").strip() or "file"
        if not link:
            continue
        try:
            if typ == "image":
                res = send_image_link(account=account, to=msg.from_number, link=link, caption=caption)
                outbound_results.append(res)
                WhatsAppMessage.objects.create(
                    owner=owner,
                    whatsapp_account=account,
                    customer=customer,
                    direction=WhatsAppMessage.Direction.OUTBOUND,
                    from_number=(account.phone_number or msg.to_number or "").strip(),
                    to_number=(msg.from_number or "").strip(),
                    body=link,
                    message_type="image",
                    provider_message_id=res.provider_message_id,
                    raw_payload={"provider": res.provider, "status_code": res.status_code, "response": res.response_text[:5000]},
                    status=WhatsAppMessage.Status.PROCESSED if res.ok else WhatsAppMessage.Status.FAILED,
                    error="" if res.ok else (res.response_text or "")[:2000],
                    parsed_intent=engine_res.intent or "",
                )
            elif typ == "document":
                res = send_document_link(account=account, to=msg.from_number, link=link, filename=filename, caption=caption)
                outbound_results.append(res)
                WhatsAppMessage.objects.create(
                    owner=owner,
                    whatsapp_account=account,
                    customer=customer,
                    direction=WhatsAppMessage.Direction.OUTBOUND,
                    from_number=(account.phone_number or msg.to_number or "").strip(),
                    to_number=(msg.from_number or "").strip(),
                    body=link,
                    message_type="document",
                    provider_message_id=res.provider_message_id,
                    raw_payload={"provider": res.provider, "status_code": res.status_code, "response": res.response_text[:5000]},
                    status=WhatsAppMessage.Status.PROCESSED if res.ok else WhatsAppMessage.Status.FAILED,
                    error="" if res.ok else (res.response_text or "")[:2000],
                    parsed_intent=engine_res.intent or "",
                )
        except Exception:
            logger.exception("Attachment send failed")

    sent_ok = any(getattr(r, "ok", False) for r in outbound_results)
    sent_failed = any(not getattr(r, "ok", False) for r in outbound_results)

    msg.parsed_intent = engine_res.intent or ""
    msg.parsed_payload = {
        "order_id": engine_res.order_id,
        "invoice_id": engine_res.invoice_id,
        "payment_url": engine_res.payment_url,
        "invoice_pdf_url": engine_res.invoice_pdf_url,
    }
    msg.reference_type = (engine_res.reference_type or ("commerce.Order" if engine_res.order_id else "")).strip()
    msg.reference_id = engine_res.reference_id or engine_res.order_id
    msg.status = WhatsAppMessage.Status.PROCESSED if sent_ok else WhatsAppMessage.Status.FAILED
    msg.error = "" if sent_ok else "send_failed"
    msg.save(update_fields=["parsed_intent", "parsed_payload", "reference_type", "reference_id", "status", "error"])

    # Best-effort: send invoice PDF as a document when available.
    invoice_pdf_url = (engine_res.invoice_pdf_url or "").strip()
    if sent_ok and invoice_pdf_url and engine_res.invoice_id:
        key = f"wa:invpdf:{account.id}:{_digits(msg.from_number)}:{engine_res.invoice_id}"
        if cache.add(key, 1, timeout=2 * 60 * 60):
            try:
                doc = send_document_link(
                    account=account,
                    to=msg.from_number,
                    link=invoice_pdf_url,
                    filename=f"invoice_{engine_res.invoice_id}.pdf",
                    caption=f"Invoice #{engine_res.invoice_id}",
                )
                outbound_results.append(doc)
                WhatsAppMessage.objects.create(
                    owner=owner,
                    whatsapp_account=account,
                    customer=customer,
                    direction=WhatsAppMessage.Direction.OUTBOUND,
                    from_number=(account.phone_number or msg.to_number or "").strip(),
                    to_number=(msg.from_number or "").strip(),
                    body=invoice_pdf_url,
                    message_type="document",
                    provider_message_id=doc.provider_message_id,
                    raw_payload={"provider": doc.provider, "status_code": doc.status_code, "response": doc.response_text[:5000]},
                    status=WhatsAppMessage.Status.PROCESSED if doc.ok else WhatsAppMessage.Status.FAILED,
                    error="" if doc.ok else (doc.response_text or "")[:2000],
                    parsed_intent="invoice_pdf",
                    parsed_payload={"invoice_id": engine_res.invoice_id, "url": invoice_pdf_url},
                    reference_type="commerce.Invoice",
                    reference_id=engine_res.invoice_id,
                )
                sent_ok = sent_ok or bool(doc.ok)
                sent_failed = sent_failed or (not bool(doc.ok))
            except Exception:
                logger.exception("Invoice PDF send failed")

    if sent_ok:
        if account.status != WhatsAppAccount.Status.CONNECTED:
            account.status = WhatsAppAccount.Status.CONNECTED
            account.save(update_fields=["status", "updated_at"])
    elif sent_failed:
        if account.status != WhatsAppAccount.Status.ERROR:
            account.status = WhatsAppAccount.Status.ERROR
            account.save(update_fields=["status", "updated_at"])

    status_code = outbound_results[0].status_code if outbound_results else 0
    provider = outbound_results[0].provider if outbound_results else account.provider
    return {"ok": sent_ok and not sent_failed, "intent": engine_res.intent, "provider": provider, "status_code": status_code}


@shared_task(bind=True, max_retries=1)
def run_broadcast_campaign(self, campaign_id: str) -> dict:
    camp = (
        BroadcastCampaign.objects.select_related("owner", "whatsapp_account")
        .filter(id=campaign_id)
        .first()
    )
    if not camp:
        return {"ok": False, "error": "campaign_not_found"}

    if camp.status in {BroadcastCampaign.Status.COMPLETED, BroadcastCampaign.Status.CANCELLED}:
        return {"ok": True, "status": camp.status}

    camp.status = BroadcastCampaign.Status.RUNNING
    camp.started_at = timezone.now()
    camp.error = ""
    camp.save(update_fields=["status", "started_at", "error", "updated_at"])

    account = camp.whatsapp_account
    owner = camp.owner

    recipients_qs = Customer.objects.filter(owner=owner, whatsapp_account=account)
    if camp.target_type == BroadcastCampaign.TargetType.CUSTOMER_TAG:
        tag = str((camp.target_payload or {}).get("tag") or "").strip().lower()
        if tag:
            recipients_qs = recipients_qs.filter(tags__contains=[tag])
    elif camp.target_type == BroadcastCampaign.TargetType.SELECTED_CUSTOMERS:
        ids = (camp.target_payload or {}).get("customer_ids") or []
        if isinstance(ids, list) and ids:
            recipients_qs = recipients_qs.filter(id__in=ids)

    recipients = list(recipients_qs.order_by("-updated_at")[:5000])
    sent = 0
    failed = 0

    for cust in recipients:
        text = (camp.text or "").strip()
        if not text:
            continue
        res = send_text(account=account, to=cust.phone_number, text=text)
        sent += 1 if res.ok else 0
        failed += 0 if res.ok else 1
        WhatsAppMessage.objects.create(
            owner=owner,
            whatsapp_account=account,
            customer=cust,
            direction=WhatsAppMessage.Direction.OUTBOUND,
            from_number=(account.phone_number or "").strip(),
            to_number=cust.phone_number,
            body=text,
            message_type=camp.message_type,
            provider_message_id=res.provider_message_id,
            raw_payload={"broadcast_id": str(camp.id), "provider": res.provider, "status_code": res.status_code},
            status=WhatsAppMessage.Status.PROCESSED if res.ok else WhatsAppMessage.Status.FAILED,
            error="" if res.ok else (res.response_text or "")[:2000],
            reference_type="whatsapp.BroadcastCampaign",
            reference_id=None,
        )

    camp.status = BroadcastCampaign.Status.COMPLETED if failed == 0 else BroadcastCampaign.Status.FAILED
    camp.finished_at = timezone.now()
    camp.stats = {"recipients": len(recipients), "sent": sent, "failed": failed}
    camp.save(update_fields=["status", "finished_at", "stats", "updated_at"])

    return {"ok": True, "status": camp.status, "sent": sent, "failed": failed}


@shared_task
def run_scheduled_broadcasts() -> dict:
    """
    Dispatch scheduled broadcast campaigns whose scheduled_at is due.

    Intended for Celery beat on server deployments.
    """
    now = timezone.now()
    due = (
        BroadcastCampaign.objects.filter(status=BroadcastCampaign.Status.SCHEDULED, scheduled_at__isnull=False, scheduled_at__lte=now)
        .order_by("scheduled_at")[:200]
    )
    started = 0
    for camp in due:
        try:
            # Mark as draft first (so run_broadcast_campaign will run and mark running/completed).
            camp.status = BroadcastCampaign.Status.DRAFT
            camp.save(update_fields=["status", "updated_at"])
            try:
                run_broadcast_campaign.apply_async(args=(str(camp.id),), retry=False, ignore_result=True)
            except Exception:
                run_broadcast_campaign.run(str(camp.id))  # type: ignore[attr-defined]
            started += 1
        except Exception:
            logger.exception("Failed to start scheduled broadcast %s", camp.id)
            continue
    return {"ok": True, "due": int(due.count() if hasattr(due, "count") else len(due)), "started": started}


@shared_task
def healthcheck_whatsapp_accounts() -> dict:
    """
    Lightweight connectivity check. Intended for Celery beat on server deployments.
    """
    checked = 0
    ok = 0
    for acc in WhatsAppAccount.objects.filter(is_active=True)[:2000]:
        checked += 1
        try:
            res = healthcheck(acc)
            if res.ok:
                ok += 1
                if acc.status != WhatsAppAccount.Status.CONNECTED:
                    acc.status = WhatsAppAccount.Status.CONNECTED
                    acc.save(update_fields=["status", "updated_at"])
            else:
                if acc.status != WhatsAppAccount.Status.ERROR:
                    acc.status = WhatsAppAccount.Status.ERROR
                    acc.save(update_fields=["status", "updated_at"])
        except Exception:
            logger.exception("WhatsApp account healthcheck failed")
    return {"checked": checked, "ok": ok}


@shared_task
def send_supplier_payment_reminders_daily() -> dict:
    """
    Daily scheduled job to message suppliers with overdue/pending purchase payments.

    Safe-by-default:
    - Sends max 1 reminder per supplier per day (cache)
    - Skips suppliers without mobile/whatsapp number
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    owners = User.objects.filter(is_active=True).only("id").iterator()
    total = {"ok": True, "owners": 0, "sent": 0, "failed": 0, "skipped": 0}
    for owner in owners:
        total["owners"] += 1
        try:
            out = send_supplier_payment_reminders(owner=owner, dry_run=False)
            total["sent"] += int(out.get("sent") or 0)
            total["failed"] += int(out.get("failed") or 0)
            total["skipped"] += int(out.get("skipped") or 0)
        except Exception:
            logger.exception("Supplier reminder daily task failed")
            continue
    return total
