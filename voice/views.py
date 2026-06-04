from __future__ import annotations

import json
import logging
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry
from voice.command_parser import parse_voice_command
from voice.models import VoiceCommand
from whatsapp.message_handler import execute_parsed_command

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


@login_required
def voice_dashboard(request):
    if not bool(_get_global_setting("ai_tools_enabled", True)) or not bool(_get_global_setting("voice_enabled", True)):
        return render(request, "voice/disabled.html", {})
    recent = VoiceCommand.objects.filter(owner=request.user).order_by("-created_at")[:30]
    return render(request, "voice/dashboard.html", {"recent": recent})


def _redirect_for_reference(reference_type: str, reference_id: int | None) -> str:
    if not reference_type or not reference_id:
        return ""
    try:
        if reference_type == "commerce.Order":
            return reverse("commerce:order_detail", kwargs={"pk": reference_id})
        if reference_type == "accounts.Expense":
            return reverse("accounts:expense_list")
        if reference_type == "khataapp.Transaction":
            return reverse("khataapp:transaction_view", kwargs={"id": reference_id})
    except Exception:
        return ""
    return ""


@login_required
@require_POST
def api_voice_command(request):
    if not bool(_get_global_setting("ai_tools_enabled", True)) or not bool(_get_global_setting("voice_enabled", True)):
        return JsonResponse({"ok": False, "error": "Voice accounting is disabled"}, status=403)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    text = str(payload.get("text") or "").strip()
    if not text:
        return JsonResponse({"ok": False, "error": "Empty text"}, status=400)

    cmd = VoiceCommand.objects.create(owner=request.user, raw_text=text, status=VoiceCommand.Status.RECEIVED)
    parsed = parse_voice_command(text)
    if not parsed:
        cmd.status = VoiceCommand.Status.FAILED
        cmd.error = "Unrecognized command"
        cmd.save(update_fields=["status", "error"])
        return JsonResponse({"ok": False, "error": "Unrecognized command"})

    cmd.parsed_intent = parsed.intent
    cmd.parsed_payload = parsed.payload
    cmd.status = VoiceCommand.Status.PARSED
    cmd.save(update_fields=["parsed_intent", "parsed_payload", "status"])

    try:
        res = execute_parsed_command(owner=request.user, parsed=parsed)
        cmd.status = VoiceCommand.Status.CREATED if res.ok else VoiceCommand.Status.FAILED
        cmd.reference_type = res.reference_type
        cmd.reference_id = res.reference_id
        cmd.error = "" if res.ok else res.reply
        cmd.save(update_fields=["status", "reference_type", "reference_id", "error"])
        return JsonResponse(
            {
                "ok": res.ok,
                "reply": res.reply,
                "intent": res.intent,
                "reference_type": res.reference_type,
                "reference_id": res.reference_id,
                "redirect_url": _redirect_for_reference(res.reference_type, res.reference_id),
            }
        )
    except Exception as e:
        logger.exception("Voice command execution failed")
        cmd.status = VoiceCommand.Status.FAILED
        cmd.error = f"{type(e).__name__}: {e}"
        cmd.save(update_fields=["status", "error"])
        return JsonResponse({"ok": False, "error": "Failed to execute command"}, status=500)
