from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from ai_ocr.data_parser import ParsedInvoice, parse_invoice_text, parse_invoice_text_llm
from ai_ocr.ocr_engine import OcrResult, extract_text_from_image_file, extract_text_from_pdf_bytes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvoiceReadResult:
    ok: bool
    ocr: OcrResult
    parsed: Optional[ParsedInvoice]


def read_invoice_from_upload(file_obj) -> InvoiceReadResult:
    name = (getattr(file_obj, "name", "") or "").lower()
    if name.endswith(".pdf"):
        try:
            pdf_bytes = file_obj.read()
        except Exception:
            pdf_bytes = b""
        ocr = extract_text_from_pdf_bytes(pdf_bytes, filename=getattr(file_obj, "name", "") or "")
    else:
        ocr = extract_text_from_image_file(file_obj)
    if not ocr.ok:
        return InvoiceReadResult(ok=False, ocr=ocr, parsed=None)

    # Prefer LLM structured parse if available, else regex heuristics.
    parsed = parse_invoice_text_llm(ocr.text) or parse_invoice_text(ocr.text)
    return InvoiceReadResult(ok=True, ocr=ocr, parsed=parsed)
