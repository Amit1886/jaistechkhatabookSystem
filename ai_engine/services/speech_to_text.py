from __future__ import annotations

import io
import os
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptionResult:
    ok: bool
    text: str
    provider: str
    error: str = ""
    raw: dict[str, Any] | None = None


def transcribe_audio_bytes(audio_bytes: bytes, *, filename: str = "audio.ogg") -> TranscriptionResult:
    """
    Speech-to-text for WhatsApp voice notes (best-effort).

    Provider order:
    1) OpenAI Whisper (requires OPENAI_API_KEY)
    2) (Optional) local engines can be added later
    """
    if not audio_bytes:
        return TranscriptionResult(ok=False, text="", provider="none", error="Empty audio")

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        # Optional offline fallback: Vosk (requires `vosk` + downloaded model).
        model_path = (os.getenv("VOSK_MODEL_PATH") or "").strip()
        if model_path:
            try:
                from vosk import Model, KaldiRecognizer  # type: ignore
                import json
                import wave

                # Vosk needs WAV PCM. If user sends OGG/OPUS, conversion is required (ffmpeg).
                # For now, support WAV input only in offline mode.
                if not filename.lower().endswith(".wav"):
                    return TranscriptionResult(
                        ok=False,
                        text="",
                        provider="vosk",
                        error="Offline voice needs WAV file. Send WAV or enable OpenAI Whisper (OPENAI_API_KEY).",
                    )
                wf = wave.open(io.BytesIO(audio_bytes), "rb")
                rec = KaldiRecognizer(Model(model_path), wf.getframerate())
                text_out = ""
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    rec.AcceptWaveform(data)
                final = json.loads(rec.FinalResult() or "{}")
                text_out = str(final.get("text") or "").strip()
                if not text_out:
                    return TranscriptionResult(ok=False, text="", provider="vosk", error="No transcript returned")
                return TranscriptionResult(ok=True, text=text_out, provider="vosk", raw={"model_path": model_path})
            except Exception as e:
                return TranscriptionResult(ok=False, text="", provider="vosk", error=f"{type(e).__name__}: {e}")

        return TranscriptionResult(ok=False, text="", provider="openai_whisper", error="OPENAI_API_KEY not set. Voice transcription requires an AI key (or configure VOSK_MODEL_PATH for offline).")

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI()
    except Exception as e:
        return TranscriptionResult(ok=False, text="", provider="openai_whisper", error=f"OpenAI client unavailable: {e}")

    model = (os.getenv("WHATSAPP_AUDIO_MODEL") or "").strip() or "whisper-1"
    try:
        f = io.BytesIO(audio_bytes)
        f.name = filename  # type: ignore[attr-defined]
        resp = client.audio.transcriptions.create(  # type: ignore[attr-defined]
            model=model,
            file=f,
        )
        text = ""
        try:
            text = (resp.text or "").strip()  # type: ignore[attr-defined]
        except Exception:
            text = str(resp or "").strip()
        if not text:
            return TranscriptionResult(ok=False, text="", provider="openai_whisper", error="No transcript returned")
        return TranscriptionResult(ok=True, text=text, provider="openai_whisper", raw={"model": model})
    except Exception as e:
        logger.exception("Audio transcription failed")
        return TranscriptionResult(ok=False, text="", provider="openai_whisper", error=f"{type(e).__name__}: {e}")
