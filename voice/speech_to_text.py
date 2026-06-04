from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpeechToTextResult:
    ok: bool
    text: str
    provider: str
    error: str = ""
    raw: dict[str, Any] | None = None


def transcribe_audio_file(file_obj) -> SpeechToTextResult:
    """
    Optional server-side transcription (OpenAI Whisper).
    Frontend typically uses Web Speech API; this is a fallback for browsers without it.
    """
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI()
    except Exception:
        return SpeechToTextResult(ok=False, text="", provider="openai_whisper", error="OpenAI client unavailable")

    try:
        # Reset pointer
        try:
            file_obj.seek(0)
        except Exception:
            pass
        resp = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=file_obj,
        )
        text = (getattr(resp, "text", "") or "").strip()
        if not text:
            return SpeechToTextResult(ok=False, text="", provider="openai_whisper", error="No transcription text")
        try:
            raw = resp.model_dump()
        except Exception:
            raw = None
        return SpeechToTextResult(ok=True, text=text, provider="openai_whisper", raw=raw)
    except Exception as e:
        logger.exception("Transcription failed")
        return SpeechToTextResult(ok=False, text="", provider="openai_whisper", error=f"{type(e).__name__}: {e}")

