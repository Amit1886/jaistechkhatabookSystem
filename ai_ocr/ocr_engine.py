from __future__ import annotations

import base64
import logging
import os
import shutil
import io
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import sync_settings_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    ok: bool
    text: str
    provider: str
    error: str = ""
    raw: dict[str, Any] | None = None


def _openai_client():
    try:
        from openai import OpenAI  # type: ignore

        return OpenAI()
    except Exception:
        return None


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


def extract_text_from_image_bytes(image_bytes: bytes, *, filename: str = "") -> OcrResult:
    """
    OCR via OpenAI Vision (no extra dependencies).

    Notes:
    - Requires `OPENAI_API_KEY` in environment.
    - In offline desktop mode, this will fail gracefully.
    """
    provider = "openai_vision"
    if not image_bytes:
        return OcrResult(ok=False, text="", provider=provider, error="Empty image")

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        # Fallback: local Tesseract OCR if installed (no API key needed).
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # pillow is already in requirements

            tcmd = (os.getenv("TESSERACT_CMD") or "").strip()
            if tcmd:
                try:
                    pytesseract.pytesseract.tesseract_cmd = tcmd  # type: ignore[attr-defined]
                except Exception:
                    pass

            if not shutil.which("tesseract") and not tcmd:
                raise RuntimeError("tesseract_not_found")

            img = Image.open(io.BytesIO(image_bytes))
            text = (pytesseract.image_to_string(img) or "").strip()
            if not text:
                return OcrResult(ok=False, text="", provider="tesseract", error="No text extracted (tesseract)")
            return OcrResult(ok=True, text=text, provider="tesseract", raw={"filename": filename})
        except Exception as e:
            return OcrResult(
                ok=False,
                text="",
                provider="tesseract",
                error=(
                    "OCR needs OPENAI_API_KEY OR local Tesseract.\n"
                    "To use offline OCR:\n"
                    "1) Install Tesseract OCR on Windows\n"
                    "2) pip install pytesseract\n"
                    "Then restart server.\n"
                    f"Error: {type(e).__name__}: {e}"
                ),
            )

    client = _openai_client()
    if not client:
        return OcrResult(ok=False, text="", provider=provider, error="OpenAI client unavailable")

    model = str(_get_global_setting("ocr_model", "") or "").strip() or "gpt-4o-mini"
    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        ext = os.path.splitext(filename or "")[1].strip().lower()
        mime = "image/jpeg"
        if ext in {".png"}:
            mime = "image/png"
        elif ext in {".webp"}:
            mime = "image/webp"
        elif ext in {".gif"}:
            mime = "image/gif"
        data_url = f"data:{mime};base64,{b64}"

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an OCR engine for invoices. Extract all visible text faithfully. Do not add commentary.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the invoice text."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0,
        )

        text = ""
        try:
            text = (resp.choices[0].message.content or "").strip()
        except Exception:
            text = ""
        if not text:
            return OcrResult(ok=False, text="", provider=provider, error="No text extracted", raw={"response": resp.model_dump()})
        return OcrResult(ok=True, text=text, provider=provider, raw={"response": resp.model_dump()})
    except Exception as e:
        logger.exception("OCR failed")
        return OcrResult(ok=False, text="", provider=provider, error=f"{type(e).__name__}: {e}")


def extract_text_from_image_file(file_obj) -> OcrResult:
    try:
        image_bytes = file_obj.read()
    except Exception:
        image_bytes = b""
    return extract_text_from_image_bytes(image_bytes, filename=getattr(file_obj, "name", "") or "")


def extract_text_from_pdf_bytes(pdf_bytes: bytes, *, filename: str = "") -> OcrResult:
    """
    Best-effort PDF extraction.

    - Prefer native text extraction via PyMuPDF (fast).
    - If PyMuPDF isn't available, returns a clear error so the UI can guide setup.
    """
    provider = "pymupdf"
    if not pdf_bytes:
        return OcrResult(ok=False, text="", provider=provider, error="Empty PDF")

    try:
        import fitz  # type: ignore
    except Exception:
        return OcrResult(ok=False, text="", provider=provider, error="PyMuPDF not installed (install pymupdf)")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = int(doc.page_count or 0)
        texts = []
        for i in range(min(3, page_count)):
            page = doc.load_page(i)
            t = (page.get_text("text") or "").strip()
            if t:
                texts.append(t)
        doc.close()
        text = "\n\n".join(texts).strip()
        if not text:
            return OcrResult(ok=False, text="", provider=provider, error="No text extracted from PDF (scanned image PDF?)")
        return OcrResult(ok=True, text=text, provider=provider, raw={"pages": min(3, page_count)})
    except Exception as e:
        logger.exception("PDF extraction failed")
        return OcrResult(ok=False, text="", provider=provider, error=f"{type(e).__name__}: {e}")
