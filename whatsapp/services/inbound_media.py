from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils import timezone

from ai_ocr.invoice_reader import read_invoice_from_upload
from commerce.services.purchase_automation import create_purchase_from_invoice
from whatsapp.models import Customer, WhatsAppAccount, WhatsAppMessage
from whatsapp.services.message_router import EngineResult

logger = logging.getLogger(__name__)


def _media_max_bytes() -> int:
    # Default 3MB to keep webhooks fast + DB safe.
    try:
        return int(os.getenv("WA_MEDIA_MAX_BYTES") or "3145728")
    except Exception:
        return 3145728


def _ext_from_mime(mime: str, fallback: str = "bin") -> str:
    m = (mime or "").lower().strip()
    if "image/jpeg" in m or "image/jpg" in m:
        return "jpg"
    if "image/png" in m:
        return "png"
    if "image/webp" in m:
        return "webp"
    if "audio/ogg" in m or "audio/opus" in m:
        return "ogg"
    if "audio/mpeg" in m:
        return "mp3"
    if "audio/wav" in m:
        return "wav"
    if "application/pdf" in m:
        return "pdf"
    return fallback


def _save_media_bytes(*, account: WhatsAppAccount, message: WhatsAppMessage, data: bytes, ext: str) -> str:
    root = getattr(settings, "MEDIA_ROOT", None)
    # Store under media/wa_media/<account>/<date>/...
    stamp = timezone.localdate().strftime("%Y%m%d")
    name = (message.provider_message_id or f"msg_{message.id}").replace("/", "_").replace("\\", "_")
    rel = f"wa_media/{account.id}/{stamp}/{name}.{ext}"
    try:
        # default_storage handles MEDIA_ROOT.
        with default_storage.open(rel, "wb") as f:
            f.write(data)
    except Exception:
        # fallback to direct path if storage is local
        if root:
            abs_path = os.path.join(str(root), rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "wb") as f:
                f.write(data)
    return rel


def _media_payload(msg: WhatsAppMessage) -> dict:
    raw = msg.raw_payload if isinstance(msg.raw_payload, dict) else {}
    media = raw.get("media") if isinstance(raw.get("media"), dict) else {}
    return media


def _decode_media_base64(b64: str) -> bytes:
    # Allow both raw base64 and data URIs.
    s = (b64 or "").strip()
    if not s:
        return b""
    if s.startswith("data:") and "base64," in s:
        s = s.split("base64,", 1)[1]
    try:
        return base64.b64decode(s, validate=False)
    except Exception:
        try:
            return base64.b64decode(s)
        except Exception:
            return b""


def _is_supplier(customer: Customer) -> bool:
    try:
        p = customer.party if customer.party_id else None
        return bool(p and getattr(p, "party_type", "") == "supplier")
    except Exception:
        return False


def handle_inbound_media_message(
    *,
    owner,
    account: WhatsAppAccount,
    customer: Customer,
    msg: WhatsAppMessage,
) -> Optional[EngineResult]:
    """
    Media-aware processing for WhatsApp gateway messages.

    Supports (MVP):
    - Supplier invoice photo -> OCR -> create purchase entry + stock update
    - Voice notes: pipeline placeholder (requires transcription provider)
    """
    typ = (msg.message_type or "").strip().lower()
    if typ not in {"image", "document", "ptt", "audio", "voice"}:
        return None

    media = _media_payload(msg)
    b64 = str(media.get("base64") or "")
    mime = str(media.get("mimetype") or "")
    size = int(media.get("size") or 0) if str(media.get("size") or "").isdigit() else 0

    if not b64:
        return None

    data = _decode_media_base64(b64)
    if not data:
        return EngineResult(ok=False, reply="Media received but could not decode file. Please try again.", intent="media_error")

    if len(data) > _media_max_bytes():
        return EngineResult(ok=False, reply="File too large. Please send a smaller image/voice note.", intent="media_too_large")

    ext = _ext_from_mime(mime, fallback="bin")
    rel_path = _save_media_bytes(account=account, message=msg, data=data, ext=ext)

    # Persist saved path for audit/debug
    try:
        raw = msg.raw_payload if isinstance(msg.raw_payload, dict) else {}
        media2 = raw.get("media") if isinstance(raw.get("media"), dict) else {}
        media2["saved_path"] = rel_path
        raw["media"] = media2
        msg.raw_payload = raw
        msg.save(update_fields=["raw_payload"])
    except Exception:
        pass

    # Supplier invoice automation (image/pdf)
    if typ in {"image", "document"} and _is_supplier(customer):
        try:
            from khataapp.models import Party

            supplier = customer.party if customer.party_id else None
            if not supplier or getattr(supplier, "party_type", "") != "supplier":
                return EngineResult(ok=False, reply="Supplier not recognized. Please register supplier in Parties.", intent="supplier_not_found")

            # Read OCR from saved file via storage
            with default_storage.open(rel_path, "rb") as f:
                result = read_invoice_from_upload(f)
            if not result.ok or not result.parsed:
                err = (result.ocr.error or "OCR failed").strip()
                return EngineResult(ok=False, reply=f"Invoice OCR failed: {err[:180]}", intent="invoice_ocr_failed")

            created = create_purchase_from_invoice(owner=owner, supplier=supplier, parsed=result.parsed, auto_update_stock=True)
            if not created.ok or not created.order:
                return EngineResult(ok=False, reply="Could not create purchase entry from invoice.", intent="purchase_create_failed")

            order = created.order
            reply = (
                f"✅ Purchase recorded\n"
                f"Supplier: {supplier.name}\n"
                f"PO: #{order.id}  Invoice: {order.invoice_number or '-'}\n"
                f"Total Due: ₹{created.total_amount}\n"
                + (f"Due Date: {order.payment_due_date}\n" if order.payment_due_date else "")
                + (f"New Products: {created.created_products}\n" if created.created_products else "")
                + "Stock updated."
            )
            return EngineResult(ok=True, reply=reply, intent="supplier_invoice_photo")
        except Exception:
            logger.exception("Supplier invoice photo automation failed")
            return EngineResult(ok=False, reply="Failed to process supplier invoice photo.", intent="supplier_invoice_error")

    # Voice notes: require transcription provider (optional)
    if typ in {"ptt", "audio", "voice"}:
        try:
            from ai_engine.services.speech_to_text import transcribe_audio_bytes

            tr = transcribe_audio_bytes(data, filename=f"{msg.id}.{ext}")
            if not tr.ok or not tr.text:
                return EngineResult(ok=False, reply=f"Voice received but transcription failed: {tr.error[:160]}", intent="voice_transcribe_failed")

            # Replace inbound text with transcript and let normal router handle.
            try:
                msg.body = tr.text
                msg.message_type = "text"
                msg.parsed_payload = dict(msg.parsed_payload or {})
                msg.parsed_payload["voice_transcript"] = tr.text
                msg.save(update_fields=["body", "message_type", "parsed_payload"])
            except Exception:
                pass
            return None  # continue normal route_inbound_message with new text
        except Exception:
            return EngineResult(ok=False, reply="Voice is not supported yet. Please send text.", intent="voice_not_supported")

    return None
