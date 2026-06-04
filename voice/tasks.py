from __future__ import annotations

import logging
import os

from celery import shared_task
from django.utils import timezone

from leads.models import Lead
from voice.models import VoiceCall
from voice.services import _execute_provider_call

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def dispatch_voice_call(self, call_id: int):
    try:
        call = VoiceCall.objects.select_related("lead").get(id=call_id)
    except VoiceCall.DoesNotExist:
        return

    if call.status not in {VoiceCall.Status.PENDING, VoiceCall.Status.DIALING}:
        return

    call.mark_started()
    _execute_provider_call(call)


@shared_task
def summarize_voice_call(call_id: int, transcription: str = "", recording_url: str = ""):
    """
    Store AI-generated summary after a voice provider posts transcription.
    """
    try:
        call = VoiceCall.objects.get(id=call_id)
    except VoiceCall.DoesNotExist:
        return

    if recording_url:
        call.recording_url = recording_url
    if transcription and not call.summary:
        call.summary = transcription[:2000]
    call.status = call.status or VoiceCall.Status.COMPLETED
    call.completed_at = call.completed_at or timezone.now()
    call.save(update_fields=["summary", "recording_url", "status", "completed_at", "updated_at"])
