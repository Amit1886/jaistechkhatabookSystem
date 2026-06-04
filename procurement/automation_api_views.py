from __future__ import annotations

import base64
import logging
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_ocr.invoice_reader import read_invoice_from_upload
from whatsapp.api_connector import verify_webhook_secret
from voice.models import VoiceCommand
from voice.speech_to_text import transcribe_audio_file
from procurement.automation_engine import (
    approve_purchase_draft,
    create_purchase_draft_from_parsed,
    process_purchase_draft,
)
from procurement.automation_serializers import PurchaseDraftSerializer
from procurement.models import InvoiceSource, PurchaseDraft, SupplierAPIConnection
from procurement.voice_purchase_parser import parse_voice_purchase

logger = logging.getLogger(__name__)
User = get_user_model()


def _digits(s: str) -> str:
    import re

    return re.sub(r"[^0-9]", "", s or "")


def _resolve_owner_from_mobile(mobile: str):
    d = _digits(mobile)
    if not d:
        return None
    if len(d) > 10:
        d = d[-10:]
    return User.objects.filter(mobile__endswith=d).order_by("-id").first()


class PurchaseDraftListAPI(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseDraftSerializer

    def get_queryset(self):
        qs = PurchaseDraft.objects.prefetch_related("items").select_related("supplier", "source", "created_order")
        if self.request.user.is_staff or self.request.user.is_superuser:
            owner_id = (self.request.query_params.get("owner_id") or "").strip()
            if owner_id:
                try:
                    return qs.filter(owner_id=int(owner_id)).order_by("-created_at", "-id")
                except Exception:
                    pass
            return qs.order_by("-created_at", "-id")
        return qs.filter(owner=self.request.user).order_by("-created_at", "-id")


class PurchaseDraftRetrieveAPI(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PurchaseDraftSerializer
    queryset = PurchaseDraft.objects.prefetch_related("items").select_related("supplier", "source", "created_order")

    def get_object(self):
        obj = super().get_object()
        if self.request.user.is_staff or self.request.user.is_superuser:
            return obj
        if obj.owner_id != self.request.user.id:
            raise permissions.PermissionDenied("Not allowed.")
        return obj


class PurchaseDraftProcessAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, draft_id: int):
        draft = get_object_or_404(PurchaseDraft, id=draft_id)
        if not (request.user.is_staff or request.user.is_superuser) and draft.owner_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        auto_mode = str(request.data.get("auto_mode") or "").strip().lower() not in {"0", "false", "no", "off"}
        try:
            thr_raw = (request.data.get("auto_approve_threshold") or "").strip()
            thr = Decimal(thr_raw) if thr_raw else Decimal("0.92")
        except Exception:
            thr = Decimal("0.92")

        processed = process_purchase_draft(draft=draft, auto_mode=auto_mode, auto_approve_threshold=thr)
        return Response(PurchaseDraftSerializer(processed).data)


class PurchaseDraftApproveAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, draft_id: int):
        draft = get_object_or_404(PurchaseDraft.objects.select_for_update(), id=draft_id)
        if not (request.user.is_staff or request.user.is_superuser) and draft.owner_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        order = approve_purchase_draft(draft=draft, auto_approved=False, approved_by=request.user)
        return Response({"ok": True, "order_id": order.id, "draft_id": draft.id})


class PurchaseCaptureOCRUploadAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded = request.FILES.get("file") or request.FILES.get("image")
        if not uploaded:
            return Response({"ok": False, "error": "Missing file"}, status=status.HTTP_400_BAD_REQUEST)

        source = InvoiceSource.objects.create(
            owner=request.user,
            source_type=InvoiceSource.SourceType.OCR_SCAN,
            file=uploaded,
            content_type=str(getattr(uploaded, "content_type", "") or "")[:120],
            status=InvoiceSource.Status.RECEIVED,
        )

        try:
            res = read_invoice_from_upload(uploaded)
            if not res.ok or not res.parsed:
                source.status = InvoiceSource.Status.FAILED
                source.error = res.ocr.error or "OCR failed"
                source.save(update_fields=["status", "error", "updated_at"])
                return Response({"ok": False, "error": source.error}, status=status.HTTP_400_BAD_REQUEST)

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
            source.raw_payload = {"parsed": parsed_dict, "provider": res.ocr.provider}
            source.status = InvoiceSource.Status.EXTRACTED
            source.save(update_fields=["extracted_text", "raw_payload", "status", "updated_at"])

            draft = create_purchase_draft_from_parsed(owner=request.user, parsed=parsed_dict, source=source)
            source.status = InvoiceSource.Status.DRAFTED
            source.save(update_fields=["status", "updated_at"])

            processed = process_purchase_draft(draft=draft, auto_mode=True)
            return Response({"ok": True, "draft": PurchaseDraftSerializer(processed).data})
        except Exception as e:
            logger.exception("OCR capture failed")
            source.status = InvoiceSource.Status.FAILED
            source.error = f"{type(e).__name__}: {e}"
            source.save(update_fields=["status", "error", "updated_at"])
            return Response({"ok": False, "error": "Failed to process invoice"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PurchaseCaptureJsonAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        supplier_name = str(payload.get("supplier_name") or "").strip()
        if not supplier_name:
            return Response({"ok": False, "error": "supplier_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        source = InvoiceSource.objects.create(
            owner=request.user,
            source_type=InvoiceSource.SourceType.API,
            content_type="application/json",
            raw_payload=payload,
            status=InvoiceSource.Status.RECEIVED,
        )
        draft = create_purchase_draft_from_parsed(owner=request.user, parsed=payload, source=source)
        processed = process_purchase_draft(draft=draft, auto_mode=True)
        return Response({"ok": True, "draft": PurchaseDraftSerializer(processed).data})


class SupplierAPIIngestInvoiceAPI(APIView):
    """
    Future-ready supplier ERP invoice ingestion.

    Auth:
      - Header: X-Supplier-Token: <token>
    """

    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        token = str(request.headers.get("X-Supplier-Token") or "").strip()
        if not token:
            return Response({"ok": False, "error": "Missing X-Supplier-Token"}, status=status.HTTP_401_UNAUTHORIZED)

        conn = SupplierAPIConnection.objects.filter(token=token, status=SupplierAPIConnection.Status.ACTIVE).select_related("owner", "supplier").first()
        if not conn:
            return Response({"ok": False, "error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data if isinstance(request.data, dict) else {}
        payload = dict(payload)
        payload.setdefault("supplier_name", getattr(conn.supplier, "name", "") or "")

        source = InvoiceSource.objects.create(
            owner=conn.owner,
            source_type=InvoiceSource.SourceType.API,
            content_type="application/json",
            external_id=str(payload.get("invoice_number") or payload.get("invoice_no") or "")[:120],
            raw_payload={"supplier_api_connection_id": conn.id, "payload": payload, "received_at": timezone.now().isoformat()},
            status=InvoiceSource.Status.RECEIVED,
        )

        draft = create_purchase_draft_from_parsed(owner=conn.owner, parsed=payload, source=source)
        draft.supplier = conn.supplier
        draft.save(update_fields=["supplier", "updated_at"])
        processed = process_purchase_draft(draft=draft, auto_mode=True)
        return Response({"ok": True, "draft_id": processed.id, "status": processed.status, "confidence": str(processed.confidence)})


class PurchaseCaptureVoiceAPI(APIView):
    """
    Voice-based purchase entry (speech-to-text optional).

    Accepts either:
      - JSON: {"text": "..."}
      - multipart/form-data with "audio" file (optional) and/or "text"
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        text = str(request.data.get("text") or "").strip()
        audio = request.FILES.get("audio")
        stt_meta: dict[str, Any] = {}
        if audio and not text:
            stt = transcribe_audio_file(audio)
            if not stt.ok:
                return Response({"ok": False, "error": stt.error or "Transcription failed"}, status=status.HTTP_400_BAD_REQUEST)
            text = stt.text
            stt_meta = {"provider": stt.provider, "raw": stt.raw}

        if not text:
            return Response({"ok": False, "error": "Missing text/audio"}, status=status.HTTP_400_BAD_REQUEST)

        cmd = VoiceCommand.objects.create(
            owner=request.user,
            raw_text=text,
            parsed_intent="purchase_draft",
            status=VoiceCommand.Status.RECEIVED,
        )

        parsed = parse_voice_purchase(text)
        if not parsed.ok:
            cmd.status = VoiceCommand.Status.FAILED
            cmd.error = parsed.error or "Unrecognized purchase command"
            cmd.save(update_fields=["status", "error"])
            return Response({"ok": False, "error": cmd.error}, status=status.HTTP_400_BAD_REQUEST)

        cmd.parsed_payload = {"supplier_name": parsed.supplier_name, "items": parsed.items}
        cmd.status = VoiceCommand.Status.PARSED
        cmd.save(update_fields=["parsed_payload", "status"])

        source = InvoiceSource.objects.create(
            owner=request.user,
            source_type=InvoiceSource.SourceType.VOICE,
            content_type="text/plain",
            extracted_text=text,
            raw_payload={"voice": cmd.parsed_payload, "stt": stt_meta},
            status=InvoiceSource.Status.EXTRACTED,
        )

        parsed_dict: dict[str, Any] = {
            "supplier_name": parsed.supplier_name,
            "invoice_no": "",
            "invoice_date": timezone.localdate().isoformat(),
            "items": parsed.items,
            "totals": {},
            "confidence": 0.55,
        }
        draft = create_purchase_draft_from_parsed(owner=request.user, parsed=parsed_dict, source=source)
        processed = process_purchase_draft(draft=draft, auto_mode=True)

        cmd.reference_type = "procurement.PurchaseDraft"
        cmd.reference_id = processed.id
        cmd.status = VoiceCommand.Status.CREATED if processed.created_order_id else VoiceCommand.Status.PARSED
        cmd.save(update_fields=["reference_type", "reference_id", "status"])
        return Response({"ok": True, "draft": PurchaseDraftSerializer(processed).data})


class PurchaseCaptureWhatsAppInvoiceWebhookAPI(APIView):
    """
    WhatsApp invoice capture (webhook stub).

    Security:
      - Uses the same secret validation as WhatsApp accounting webhook:
        header `X-WA-Secret` or query param `secret`.

    Expected JSON (flexible keys):
    {
      "from": "9199xxxxxxx",
      "message_id": "....",
      "file_base64": "<base64>",
      "mime_type": "image/jpeg",
      "filename": "invoice.jpg"
    }
    """

    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]

    def post(self, request):
        provided_secret = (request.headers.get("X-WA-Secret") or request.GET.get("secret") or "").strip()
        if not verify_webhook_secret(provided_secret):
            return Response({"ok": False, "error": "Invalid secret"}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data if isinstance(request.data, dict) else {}
        from_number = str(payload.get("from") or payload.get("mobile") or payload.get("sender") or "").strip()
        owner = _resolve_owner_from_mobile(from_number)
        if not owner:
            return Response({"ok": False, "error": "Unable to resolve owner for this sender"}, status=status.HTTP_400_BAD_REQUEST)

        msg_id = str(payload.get("message_id") or payload.get("id") or payload.get("external_id") or "")[:120]
        mime = str(payload.get("mime_type") or payload.get("content_type") or "")[:120]
        filename = str(payload.get("filename") or "whatsapp-invoice")[:80]
        b64 = str(payload.get("file_base64") or "").strip()
        if not b64:
            source = InvoiceSource.objects.create(
                owner=owner,
                source_type=InvoiceSource.SourceType.WHATSAPP,
                external_id=msg_id,
                content_type=mime,
                raw_payload=payload,
                status=InvoiceSource.Status.RECEIVED,
            )
            return Response({"ok": True, "source_id": source.id, "status": source.status})

        try:
            data = base64.b64decode(b64)
        except Exception:
            return Response({"ok": False, "error": "Invalid file_base64"}, status=status.HTTP_400_BAD_REQUEST)

        if len(data) > 10 * 1024 * 1024:
            return Response({"ok": False, "error": "File too large"}, status=status.HTTP_400_BAD_REQUEST)

        source = InvoiceSource.objects.create(
            owner=owner,
            source_type=InvoiceSource.SourceType.WHATSAPP,
            external_id=msg_id,
            content_type=mime,
            raw_payload=payload,
            status=InvoiceSource.Status.RECEIVED,
        )
        try:
            # Persist file
            source.file.save(filename, ContentFile(data), save=True)
            source.status = InvoiceSource.Status.RECEIVED
            source.save(update_fields=["status", "updated_at"])

            try:
                source.file.open("rb")
                source.file.seek(0)
            except Exception:
                pass
            res = read_invoice_from_upload(source.file)
            if not res.ok or not res.parsed:
                source.status = InvoiceSource.Status.FAILED
                source.error = res.ocr.error or "OCR failed"
                source.save(update_fields=["status", "error", "updated_at"])
                return Response({"ok": False, "error": source.error}, status=status.HTTP_400_BAD_REQUEST)

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
            source.status = InvoiceSource.Status.DRAFTED
            source.save(update_fields=["status", "updated_at"])

            processed = process_purchase_draft(draft=draft, auto_mode=True)
            return Response({"ok": True, "draft_id": processed.id, "status": processed.status, "confidence": str(processed.confidence)})
        except Exception as e:
            logger.exception("WhatsApp invoice webhook processing failed")
            source.status = InvoiceSource.Status.FAILED
            source.error = f"{type(e).__name__}: {e}"
            source.save(update_fields=["status", "error", "updated_at"])
            return Response({"ok": False, "error": "Failed to process WhatsApp invoice"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
