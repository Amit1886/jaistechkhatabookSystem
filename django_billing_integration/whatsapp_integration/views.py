from __future__ import annotations

import os
from datetime import datetime

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from whatsapp_integration.models import MessageLog, TemplateMessage, WhatsAppSession
from whatsapp_integration.services.gateway_client import request_qr, send_bulk, send_message
from whatsapp_integration.services.templates import render_template


def dashboard(request: HttpRequest) -> HttpResponse:
    session_id = (os.getenv("WA_SESSION_ID") or "default").strip()
    session, _ = WhatsAppSession.objects.get_or_create(session_id=session_id, defaults={"status": WhatsAppSession.Status.NEW})

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "request_qr":
            # For a real deployment, use your public webhook URL here.
            webhook_url = request.build_absolute_uri(reverse("whatsapp_integration:webhook_incoming"))
            secret = (os.getenv("WA_WEBHOOK_SECRET") or "").strip()
            resp = request_qr(webhook_url=webhook_url, webhook_secret=secret)
            session.qr_payload = resp.text.strip()
            session.last_qr_at = datetime.utcnow()
            session.status = WhatsAppSession.Status.CONNECTED if session.qr_payload.lower() == "connected" else WhatsAppSession.Status.QR_REQUIRED
            session.last_error = "" if resp.ok else (resp.text or "")[:2000]
            session.save(update_fields=["qr_payload", "last_qr_at", "status", "last_error", "updated_at"])
            messages.success(request, "QR requested." if session.status != WhatsAppSession.Status.CONNECTED else "Already connected.")
            return redirect(request.path)

        if action == "send_message":
            phone = (request.POST.get("phone") or "").strip()
            text = (request.POST.get("message") or "").strip()
            if not phone or not text:
                messages.error(request, "Phone + message required.")
                return redirect(request.path)
            resp = send_message(phone=phone, message=text)
            MessageLog.objects.create(direction=MessageLog.Direction.OUTBOUND, phone=phone, message=text, status="sent" if resp.ok else "failed", raw_payload={"resp": resp.text})
            messages.success(request, "Sent." if resp.ok else "Send failed.")
            return redirect(request.path)

        if action == "send_bulk":
            raw = (request.POST.get("numbers") or "").strip()
            text = (request.POST.get("message") or "").strip()
            nums = [n.strip() for n in raw.split(",") if n.strip()]
            resp = send_bulk(numbers=nums, message=text)
            messages.success(request, "Bulk started." if resp.ok else "Bulk failed.")
            return redirect(request.path)

        if action == "send_template":
            phone = (request.POST.get("phone") or "").strip()
            name = (request.POST.get("template") or "").strip()
            data_raw = (request.POST.get("data_json") or "").strip()
            tpl = TemplateMessage.objects.filter(name=name, is_active=True).first()
            if not tpl:
                messages.error(request, "Template not found.")
                return redirect(request.path)
            try:
                import json

                data = json.loads(data_raw) if data_raw else {}
            except Exception:
                data = {}
            msg = render_template(tpl.text, data)
            resp = send_message(phone=phone, message=msg)
            MessageLog.objects.create(direction=MessageLog.Direction.OUTBOUND, phone=phone, message=msg, status="sent" if resp.ok else "failed", raw_payload={"template": name, "data": data, "resp": resp.text})
            messages.success(request, "Sent." if resp.ok else "Send failed.")
            return redirect(request.path)

    logs = list(MessageLog.objects.order_by("-created_at", "-id")[:200])
    templates = list(TemplateMessage.objects.filter(is_active=True).order_by("name")[:200])
    return render(request, "whatsapp_integration/dashboard.html", {"session": session, "logs": logs, "templates": templates})


@csrf_exempt
def webhook_incoming(request: HttpRequest) -> JsonResponse:
    # Optional: verify secret header
    expected = (os.getenv("WA_WEBHOOK_SECRET") or "").strip()
    provided = (request.headers.get("X-WA-Secret") or "").strip()
    if expected and provided != expected:
        return JsonResponse({"ok": False, "error": "invalid_secret"}, status=401)

    try:
        import json

        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    phone = str(payload.get("from") or payload.get("phone") or "").strip()
    name = str(payload.get("name") or "").strip()
    msg = str(payload.get("body") or payload.get("message") or "").strip()
    mtype = str(payload.get("type") or "text").strip()
    mid = str(payload.get("message_id") or "").strip()
    MessageLog.objects.create(
        direction=MessageLog.Direction.INBOUND,
        phone=phone,
        name=name,
        message=msg,
        message_type=mtype,
        provider_message_id=mid,
        raw_payload=payload,
        status="received",
    )

    # MODULE 9: basic auto reply (example)
    if msg.lower().strip() == "price":
        send_message(phone=phone, message="Please contact support for pricing.")

    return JsonResponse({"ok": True})

