from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import User
from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry
from whatsapp.api_connector import verify_webhook_secret
from whatsapp.forms import WhatsAppCommandForm, WhatsAppSettingsForm
from whatsapp.message_handler import handle_inbound_message
from whatsapp.models import WhatsAppMessage

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


def _set_global_setting(key: str, value: Any, *, by_user) -> None:
    try:
        sync_settings_registry()
    except Exception:
        pass
    definition = SettingDefinition.objects.filter(key=key).first()
    if not definition:
        return
    SettingValue.objects.update_or_create(
        definition=definition,
        owner=None,
        defaults={"value": value, "updated_by": by_user},
    )


def _mask(value: str, keep_last: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep_last:
        return "*" * len(value)
    return ("*" * (len(value) - keep_last)) + value[-keep_last:]


def _digits(s: str) -> str:
    return re.sub(r"[^0-9]", "", s or "")


def _resolve_owner_from_mobile(mobile: str) -> Optional[User]:
    d = _digits(mobile)
    if not d:
        return None
    # Match last 10 digits to support country code inputs.
    if len(d) > 10:
        d10 = d[-10:]
        return User.objects.filter(mobile__endswith=d10).order_by("-id").first()
    return User.objects.filter(mobile__endswith=d).order_by("-id").first()


@login_required
def whatsapp_accounting_dashboard(request):
    if not bool(_get_global_setting("ai_tools_enabled", True)):
        messages.error(request, "AI Tools are disabled by admin settings.")
        return redirect("accounts:dashboard")

    settings_initial = {
        "enabled": bool(_get_global_setting("wa_enabled", True)),
        "provider": str(_get_global_setting("wa_provider", "ultramsg") or "ultramsg"),
        "ultramsg_instance_id": str(_get_global_setting("wa_ultramsg_instance_id", "") or ""),
        "ultramsg_token": str(_get_global_setting("wa_ultramsg_token", "") or ""),
        "webhook_secret": str(_get_global_setting("wa_webhook_secret", "") or ""),
    }

    settings_form = WhatsAppSettingsForm(request.POST or None, initial=settings_initial, prefix="s")
    cmd_form = WhatsAppCommandForm(request.POST or None, prefix="c")

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "save_settings":
            if not request.user.is_staff:
                messages.error(request, "Only admin/staff can update WhatsApp API settings.")
                return redirect(request.path)
            if settings_form.is_valid():
                _set_global_setting("wa_enabled", bool(settings_form.cleaned_data.get("enabled")), by_user=request.user)
                _set_global_setting("wa_provider", settings_form.cleaned_data.get("provider") or "ultramsg", by_user=request.user)
                _set_global_setting("wa_ultramsg_instance_id", settings_form.cleaned_data.get("ultramsg_instance_id") or "", by_user=request.user)
                _set_global_setting("wa_ultramsg_token", settings_form.cleaned_data.get("ultramsg_token") or "", by_user=request.user)
                _set_global_setting("wa_webhook_secret", settings_form.cleaned_data.get("webhook_secret") or "", by_user=request.user)
                messages.success(request, "WhatsApp settings updated.")
                return redirect(request.path)

        if action == "simulate":
            if not bool(_get_global_setting("wa_enabled", True)):
                messages.error(request, "WhatsApp automation is disabled by admin settings.")
                return redirect(request.path)
            if cmd_form.is_valid():
                cmd = cmd_form.cleaned_data["command"]
                res = handle_inbound_message(
                    owner=request.user,
                    from_number=getattr(request.user, "mobile", "") or "",
                    to_number="",
                    body=cmd,
                    raw_payload={"source": "dashboard_simulator"},
                )
                if res.ok:
                    messages.success(request, res.reply)
                else:
                    messages.error(request, res.reply)
                return redirect(request.path)

    logs = WhatsAppMessage.objects.filter(owner=request.user).order_by("-created_at")[:50]
    webhook_url = request.build_absolute_uri(reverse("whatsapp_accounting_webhook"))
    unified_webhook_url = request.build_absolute_uri(reverse("whatsapp_unified_webhook"))
    if request.user.is_staff:
        secret = (settings_initial.get("webhook_secret") or "").strip()
        if secret:
            webhook_url = f"{webhook_url}?secret={secret}"
            unified_webhook_url = f"{unified_webhook_url}?secret={secret}"
    return render(
        request,
        "whatsapp/dashboard.html",
        {
            "settings_form": settings_form,
            "cmd_form": cmd_form,
            "logs": logs,
            "webhook_url": webhook_url,
            "unified_webhook_url": unified_webhook_url,
            "masked_token": _mask(settings_initial.get("ultramsg_token", "")),
            "masked_secret": _mask(settings_initial.get("webhook_secret", "")),
        },
    )


@csrf_exempt
@require_POST
def whatsapp_accounting_webhook(request):
    """
    Provider webhook to ingest WhatsApp messages and create accounting entries.

    Expected JSON (flexible keys):
    {
      "from": "9199xxxxxxx",
      "to": "91xxxxxxxxxx",
      "body": "expense diesel 500"
    }
    Optional:
    - owner_id
    - secret (or header X-WA-Secret)
    """
    provided_secret = (request.headers.get("X-WA-Secret") or request.GET.get("secret") or "").strip()
    if not verify_webhook_secret(provided_secret):
        return JsonResponse({"ok": False, "error": "Invalid secret"}, status=403)

    if not bool(_get_global_setting("ai_tools_enabled", True)):
        return JsonResponse({"ok": False, "error": "AI Tools disabled"}, status=403)

    if not bool(_get_global_setting("wa_enabled", True)):
        return JsonResponse({"ok": False, "error": "WhatsApp automation disabled"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    body = str(payload.get("body") or payload.get("message") or payload.get("text") or "").strip()
    from_number = str(payload.get("from") or payload.get("mobile") or payload.get("sender") or "").strip()
    to_number = str(payload.get("to") or payload.get("receiver") or "").strip()

    owner = _resolve_owner_from_mobile(from_number)
    if not owner:
        return JsonResponse({"ok": False, "error": "Unable to resolve owner for this sender"}, status=400)

    owner_id = payload.get("owner_id")
    if owner_id:
        try:
            provided_owner_id = int(owner_id)
        except Exception:
            provided_owner_id = None
        if provided_owner_id and int(owner.id) != int(provided_owner_id):
            return JsonResponse({"ok": False, "error": "owner_id does not match sender"}, status=400)
    if not body:
        return JsonResponse({"ok": False, "error": "Empty message"}, status=400)

    res = handle_inbound_message(owner=owner, from_number=from_number, to_number=to_number, body=body, raw_payload=payload)
    return JsonResponse({"ok": res.ok, "reply": res.reply, "intent": res.intent, "reference_type": res.reference_type, "reference_id": res.reference_id})


def _resolve_owner_for_whatsapp_payload(payload: dict[str, Any]) -> Optional[User]:
    """
    Best-effort owner (tenant) resolver for unified WhatsApp webhook.

    Priority:
      1) explicit owner_id
      2) `to` number matches a User.mobile
      3) `from` number matches a User.mobile (owner texting automation)
      4) `from` matches a Party (customer/supplier) -> use Party.owner
      5) single-tenant fallback: first superuser/staff
    """
    owner = None

    owner_id = payload.get("owner_id") or payload.get("tenant_id") or payload.get("business_id")
    if owner_id:
        try:
            owner = User.objects.filter(id=int(owner_id)).order_by("-id").first()
        except Exception:
            owner = None
        if owner:
            return owner

    to_number = str(payload.get("to") or payload.get("receiver") or payload.get("to_number") or "").strip()
    if to_number:
        owner = _resolve_owner_from_mobile(to_number)
        if owner:
            return owner

    from_number = str(payload.get("from") or payload.get("mobile") or payload.get("sender") or "").strip()
    if from_number:
        owner = _resolve_owner_from_mobile(from_number)
        if owner:
            return owner

        try:
            from khataapp.models import Party

            d = _digits(from_number)
            d10 = d[-10:] if d else ""
            if d10:
                parties = list(
                    Party.objects.filter(Q(whatsapp_number__endswith=d10) | Q(mobile__endswith=d10))
                    .select_related("owner")
                    .order_by("-id")[:10]
                )
                owner_ids = {int(p.owner_id) for p in parties if getattr(p, "owner_id", None)}
                if len(owner_ids) == 1:
                    return parties[0].owner
        except Exception:
            pass

    # Fallback: single-tenant default
    return (
        User.objects.filter(is_superuser=True).order_by("id").first()
        or User.objects.filter(is_staff=True).order_by("id").first()
    )


@csrf_exempt
@require_POST
def whatsapp_unified_webhook(request):
    """
    Central WhatsApp webhook router (single endpoint).

    Supports:
      - Customer ordering bot (product list + cart) via commerce WhatsApp flow
      - Supplier invoice upload -> AR-CSSPS purchase draft (user approval later)
      - Owner accounting commands (expense/sale/payment) via existing WhatsApp accounting handler

    Security:
      - Header: X-WA-Secret or query param ?secret=
    """
    provided_secret = (request.headers.get("X-WA-Secret") or request.GET.get("secret") or "").strip()
    if not verify_webhook_secret(provided_secret):
        return JsonResponse({"ok": False, "error": "Invalid secret"}, status=403)

    if not bool(_get_global_setting("ai_tools_enabled", True)):
        return JsonResponse({"ok": False, "error": "AI Tools disabled"}, status=403)
    if not bool(_get_global_setting("wa_enabled", True)):
        return JsonResponse({"ok": False, "error": "WhatsApp automation disabled"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    payload = payload if isinstance(payload, dict) else {}

    # Many providers (including UltraMsg) can post outbound messages back to webhook.
    # Ignore them to prevent loops / unintended routing.
    from_me = payload.get("fromMe")
    if from_me is None:
        from_me = payload.get("from_me")
    if str(from_me).strip().lower() in {"1", "true", "yes"}:
        return JsonResponse({"ok": True, "mode": "ignored_outbound"})

    from_number = str(payload.get("from") or payload.get("mobile") or payload.get("sender") or "").strip()
    to_number = str(payload.get("to") or payload.get("receiver") or payload.get("to_number") or "").strip()
    body = str(payload.get("body") or payload.get("message") or payload.get("text") or "").strip()

    owner = _resolve_owner_for_whatsapp_payload(payload)
    if not owner:
        return JsonResponse({"ok": False, "error": "Unable to resolve owner (pass owner_id or configure routing)"}, status=400)

    # Attachment detection (base64 or URL)
    file_b64 = str(payload.get("file_base64") or payload.get("media_base64") or payload.get("document_base64") or "").strip()
    mime_type = str(payload.get("mime_type") or payload.get("content_type") or "").strip()
    filename = str(payload.get("filename") or "whatsapp-upload").strip()[:80]

    file_url = str(payload.get("file_url") or payload.get("media_url") or payload.get("document_url") or "").strip()
    if not file_url:
        media_obj = payload.get("media")
        if isinstance(media_obj, dict):
            file_url = str(media_obj.get("url") or media_obj.get("link") or media_obj.get("download_url") or "").strip()
            if (not filename) or filename == "whatsapp-upload":
                filename = str(media_obj.get("filename") or filename).strip()[:80]
            if not mime_type:
                mime_type = str(media_obj.get("mime_type") or media_obj.get("content_type") or "").strip()
        elif isinstance(media_obj, list) and media_obj:
            first = media_obj[0]
            if isinstance(first, dict):
                file_url = str(first.get("url") or first.get("link") or first.get("download_url") or "").strip()
                if (not filename) or filename == "whatsapp-upload":
                    filename = str(first.get("filename") or filename).strip()[:80]
                if not mime_type:
                    mime_type = str(first.get("mime_type") or first.get("content_type") or "").strip()

    msg_type = str(payload.get("type") or payload.get("message_type") or payload.get("msg_type") or "").strip().lower()
    if not file_url and msg_type in {"image", "document", "file"} and body.lower().startswith(("http://", "https://")):
        # Some providers put the media URL in body for file messages.
        file_url = body.strip()

    message_id = str(payload.get("message_id") or payload.get("id") or payload.get("external_id") or "")[:120]

    # 0) Owner approval commands for purchase drafts (WhatsApp-based approval layer)
    if body and from_number and _resolve_owner_from_mobile(from_number):
        cmd = body.strip().lower()
        m = re.match(r"^(approve|reject)\s*(?:draft|purchase)?\s*#?\s*(\d+)\s*$", cmd)
        if m:
            action = m.group(1)
            try:
                draft_id = int(m.group(2))
            except Exception:
                draft_id = None
            if draft_id:
                try:
                    from procurement.models import AITrainingLog, PurchaseDraft
                    from procurement.automation_engine import approve_purchase_draft

                    draft = PurchaseDraft.objects.filter(id=draft_id, owner=owner).first()
                    if not draft:
                        return JsonResponse({"ok": False, "mode": "purchase_approval", "reply": f"Draft #{draft_id} not found."}, status=404)

                    if action == "reject":
                        draft.status = PurchaseDraft.Status.REJECTED
                        draft.auto_approved = False
                        draft.save(update_fields=["status", "auto_approved", "updated_at"])
                        try:
                            AITrainingLog.objects.create(
                                owner=owner,
                                event_type=AITrainingLog.EventType.DRAFT_REJECTED,
                                reference_type="procurement.PurchaseDraft",
                                reference_id=draft.id,
                                payload={"via": "whatsapp"},
                            )
                        except Exception:
                            pass
                        return JsonResponse({"ok": True, "mode": "purchase_approval", "reply": f"Rejected Draft #{draft.id}."})

                    order = approve_purchase_draft(draft=draft, auto_approved=False, approved_by=owner)
                    return JsonResponse(
                        {
                            "ok": True,
                            "mode": "purchase_approval",
                            "reply": f"Approved Draft #{draft.id}. Purchase created: Order #{order.id}.",
                            "order_id": order.id,
                            "draft_id": draft.id,
                        }
                    )
                except Exception:
                    logger.exception("WhatsApp draft approval failed")
                    return JsonResponse({"ok": False, "mode": "purchase_approval", "reply": "Failed to process approval command."}, status=500)

    # 1) Supplier invoice capture when media is present.
    if file_b64 or file_url:
        try:
            import base64

            from django.core.files.base import ContentFile

            from ai_ocr.invoice_reader import read_invoice_from_upload
            from procurement.automation_engine import create_purchase_draft_from_parsed, process_purchase_draft
            from procurement.models import InvoiceSource
            from khataapp.models import Party

            data = b""
            if file_b64:
                cleaned = file_b64
                if cleaned.lower().startswith("data:") and "base64," in cleaned.lower():
                    cleaned = cleaned.split(",", 1)[-1]
                data = base64.b64decode(cleaned.strip())
            elif file_url:
                import requests

                parsed_url = urlparse(file_url)
                if parsed_url.scheme not in {"http", "https"}:
                    raise ValueError("unsupported_media_url_scheme")
                host = (parsed_url.hostname or "").strip().lower()
                if not host or host in {"localhost"}:
                    raise ValueError("invalid_media_url_host")
                ip = None
                try:
                    ip = ipaddress.ip_address(host)
                except ValueError:
                    ip = None
                if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast):
                    raise ValueError("blocked_media_url_host")

                r = requests.get(file_url, timeout=20, stream=True)
                if not r.ok:
                    raise ValueError(f"download_failed:{r.status_code}")
                if not mime_type:
                    mime_type = str(r.headers.get("Content-Type") or "").strip()
                if (not filename) or filename == "whatsapp-upload":
                    bn = os.path.basename(parsed_url.path or "")
                    if bn:
                        filename = bn[:80]

                buf = bytearray()
                for chunk in r.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    buf.extend(chunk)
                    if len(buf) > 10 * 1024 * 1024:
                        raise ValueError("file_too_large")
                data = bytes(buf)
        except Exception:
            logger.exception("WhatsApp invoice attachment decode/download failed")
            return JsonResponse({"ok": False, "error": "Invalid invoice attachment"}, status=400)

        if len(data) > 10 * 1024 * 1024:
            return JsonResponse({"ok": False, "error": "File too large"}, status=400)

        source = InvoiceSource.objects.create(
            owner=owner,
            source_type=InvoiceSource.SourceType.WHATSAPP,
            external_id=message_id,
            content_type=mime_type[:120],
            raw_payload=payload,
            status=InvoiceSource.Status.RECEIVED,
        )
        try:
            source.file.save(filename, ContentFile(data), save=True)
        except Exception:
            pass

        ct_l = (mime_type or "").strip().lower()
        if ct_l == "application/pdf" or str(filename).strip().lower().endswith(".pdf"):
            source.status = InvoiceSource.Status.RECEIVED
            source.error = "PDF received. For demo OCR, please send invoice as image (jpg/png)."
            source.save(update_fields=["status", "error", "updated_at"])
            return JsonResponse(
                {
                    "ok": True,
                    "mode": "supplier_invoice",
                    "reply": "PDF received. Please send invoice as an image (jpg/png) for auto-entry.",
                    "source_id": source.id,
                    "status": source.status,
                }
            )

        try:
            try:
                if source.file:
                    source.file.open("rb")
                    source.file.seek(0)
            except Exception:
                pass

            res = read_invoice_from_upload(source.file or ContentFile(data, name=filename))
            if not res.ok or not res.parsed:
                source.status = InvoiceSource.Status.FAILED
                source.error = res.ocr.error or "OCR failed"
                source.save(update_fields=["status", "error", "updated_at"])
                return JsonResponse({"ok": False, "error": source.error}, status=400)

            parsed = res.parsed
            parsed_dict: dict[str, Any] = {
                "supplier_name": parsed.supplier_name,
                "invoice_no": parsed.invoice_no,
                "invoice_date": parsed.invoice_date,
                "items": parsed.items,
                "totals": parsed.totals,
                "confidence": parsed.confidence,
            }
            source.extracted_text = res.ocr.text or ""
            source.raw_payload = {"parsed": parsed_dict, "provider": res.ocr.provider, "wa": payload}
            source.status = InvoiceSource.Status.EXTRACTED
            source.save(update_fields=["extracted_text", "raw_payload", "status", "updated_at"])

            draft = create_purchase_draft_from_parsed(owner=owner, parsed=parsed_dict, source=source)

            # Prefer mapping supplier by WhatsApp/mobile when possible.
            d10 = _digits(from_number)[-10:] if from_number else ""
            supplier = None
            if d10:
                supplier = Party.objects.filter(owner=owner, party_type="supplier", whatsapp_number__endswith=d10).order_by("-id").first()
                if not supplier:
                    supplier = Party.objects.filter(owner=owner, party_type="supplier", mobile__endswith=d10).order_by("-id").first()
            if not supplier and parsed.supplier_name:
                supplier = Party.objects.filter(owner=owner, party_type="supplier", name__iexact=str(parsed.supplier_name).strip()).first()
            if not supplier and (parsed.supplier_name or d10):
                supplier = Party.objects.create(
                    owner=owner,
                    party_type="supplier",
                    name=(str(parsed.supplier_name).strip() or f"WhatsApp Supplier {d10[-4:]}" if d10 else "WhatsApp Supplier")[:100],
                    mobile=d10[:15] if d10 else "",
                    whatsapp_number=d10[:15] if d10 else "",
                )
            if supplier:
                draft.supplier = supplier
                draft.save(update_fields=["supplier", "updated_at"])

            # Process but do NOT auto-approve for supplier invoices (approval required).
            processed = process_purchase_draft(draft=draft, auto_mode=False)
            source.status = InvoiceSource.Status.DRAFTED
            source.save(update_fields=["status", "updated_at"])

            # Notify owner (best-effort) so approval can happen quickly.
            try:
                from whatsapp.api_connector import send_whatsapp_message

                owner_mobile = (getattr(owner, "mobile", "") or "").strip().lstrip("+")
                if owner_mobile:
                    msg = (
                        f"New supplier invoice received.\n"
                        f"Draft #{processed.id}\n"
                        f"Supplier: {getattr(processed.supplier, 'name', processed.supplier_name) or '-'}\n"
                        f"Total: Rs. {processed.total_amount}\n"
                        f"Confidence: {processed.confidence}\n\n"
                        f"Reply: approve {processed.id}  OR  reject {processed.id}"
                    )
                    send_whatsapp_message(to=owner_mobile, message=msg)
            except Exception:
                pass

            reply = f"Invoice received (Draft #{processed.id}). Waiting for business approval."
            return JsonResponse(
                {
                    "ok": True,
                    "mode": "supplier_invoice",
                    "reply": reply,
                    "draft_id": processed.id,
                    "draft_status": processed.status,
                    "confidence": str(processed.confidence),
                }
            )
        except Exception as e:
            logger.exception("Unified WhatsApp invoice processing failed")
            try:
                source.status = InvoiceSource.Status.FAILED
                source.error = f"{type(e).__name__}: {e}"
                source.save(update_fields=["status", "error", "updated_at"])
            except Exception:
                pass
            return JsonResponse({"ok": False, "error": "Failed to process invoice"}, status=500)

    # 2) Owner accounting commands (if sender looks like owner user)
    if from_number and _resolve_owner_from_mobile(from_number) and body:
        res = handle_inbound_message(owner=owner, from_number=from_number, to_number=to_number, body=body, raw_payload=payload)
        return JsonResponse(
            {
                "ok": res.ok,
                "mode": "accounting",
                "reply": res.reply,
                "intent": res.intent,
                "reference_type": res.reference_type,
                "reference_id": res.reference_id,
            },
            status=200 if res.ok else 400,
        )

    # 3) Customer ordering bot (commerce WhatsApp cart flow)
    if not bool(_get_global_setting("order_via_whatsapp", False)):
        return JsonResponse({"ok": False, "mode": "order_bot", "reply": "Ordering via WhatsApp is disabled."}, status=403)

    try:
        from commerce.services.whatsapp_conversation import handle_whatsapp_order_message

        mobile_raw = from_number or str(payload.get("mobile") or "").strip()
        d = _digits(mobile_raw)
        mobile = (d[-10:] if len(d) > 10 else d) or mobile_raw
        customer_name = str(payload.get("customer_name") or payload.get("name") or "").strip()
        address = str(payload.get("address") or "").strip()

        res = handle_whatsapp_order_message(
            owner=owner,
            mobile_number=mobile,
            message=body,
            customer_name=customer_name,
            address=address,
        )
        return JsonResponse(
            {"ok": res.ok, "mode": res.mode or "order_bot", "reply": res.reply, "order_id": res.order_id, "invoice_id": res.invoice_id},
            status=200 if res.ok else 400,
        )
    except Exception:
        logger.exception("Unified WhatsApp order bot routing failed")
        return JsonResponse({"ok": False, "mode": "order_bot", "reply": "Failed to process order message."}, status=500)
