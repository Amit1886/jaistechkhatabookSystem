from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendResult:
    ok: bool
    status_code: int
    response_text: str
    message_id: str = ""


class MetaCloudWhatsAppClient:
    def __init__(self, *, phone_number_id: str, access_token: str, graph_version: str = "v20.0") -> None:
        self.phone_number_id = (phone_number_id or "").strip()
        self.access_token = (access_token or "").strip()
        self.graph_version = (graph_version or "v20.0").strip() or "v20.0"

    def _url(self, path: str) -> str:
        path = path.lstrip("/")
        return f"https://graph.facebook.com/{self.graph_version}/{path}"

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    def send_text(self, *, to: str, text: str, preview_url: bool = False) -> SendResult:
        to = (to or "").strip().lstrip("+")
        text = (text or "").strip()
        if not to or not text:
            return SendResult(ok=False, status_code=400, response_text="Missing to/text")
        url = self._url(f"{self.phone_number_id}/messages")
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": bool(preview_url)},
        }
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=20)
            msg_id = ""
            try:
                data = resp.json() if resp.text else {}
                msgs = data.get("messages") if isinstance(data, dict) else None
                if isinstance(msgs, list) and msgs:
                    msg_id = str(msgs[0].get("id") or "")
            except Exception:
                msg_id = ""
            return SendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text, message_id=msg_id)
        except Exception as e:
            logger.exception("Meta Cloud API send_text failed")
            return SendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")

    def send_document_link(self, *, to: str, link: str, filename: str = "document.pdf", caption: str = "") -> SendResult:
        to = (to or "").strip().lstrip("+")
        link = (link or "").strip()
        if not to or not link:
            return SendResult(ok=False, status_code=400, response_text="Missing to/link")
        url = self._url(f"{self.phone_number_id}/messages")
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": {"link": link, "filename": (filename or "document.pdf")[:80]},
        }
        if caption:
            payload["document"]["caption"] = str(caption)[:1024]
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=20)
            msg_id = ""
            try:
                data = resp.json() if resp.text else {}
                msgs = data.get("messages") if isinstance(data, dict) else None
                if isinstance(msgs, list) and msgs:
                    msg_id = str(msgs[0].get("id") or "")
            except Exception:
                msg_id = ""
            return SendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text, message_id=msg_id)
        except Exception as e:
            logger.exception("Meta Cloud API send_document_link failed")
            return SendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")

    def send_image_link(self, *, to: str, link: str, caption: str = "") -> SendResult:
        to = (to or "").strip().lstrip("+")
        link = (link or "").strip()
        if not to or not link:
            return SendResult(ok=False, status_code=400, response_text="Missing to/link")
        url = self._url(f"{self.phone_number_id}/messages")
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": {"link": link},
        }
        if caption:
            payload["image"]["caption"] = str(caption)[:1024]
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=20)
            msg_id = ""
            try:
                data = resp.json() if resp.text else {}
                msgs = data.get("messages") if isinstance(data, dict) else None
                if isinstance(msgs, list) and msgs:
                    msg_id = str(msgs[0].get("id") or "")
            except Exception:
                msg_id = ""
            return SendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text, message_id=msg_id)
        except Exception as e:
            logger.exception("Meta Cloud API send_image_link failed")
            return SendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")

    def healthcheck(self) -> SendResult:
        if not self.phone_number_id or not self.access_token:
            return SendResult(ok=False, status_code=400, response_text="Missing phone_number_id/access_token")
        url = self._url(f"{self.phone_number_id}?fields=display_phone_number,verified_name")
        try:
            resp = requests.get(url, headers=self._headers(), timeout=15)
            return SendResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text)
        except Exception as e:
            logger.exception("Meta Cloud API healthcheck failed")
            return SendResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")


def verify_meta_signature(*, app_secret: str, payload_bytes: bytes, provided_signature: Optional[str]) -> bool:
    """
    Verify Meta webhook signature header: X-Hub-Signature-256: sha256=<hex>
    """
    import hmac
    import hashlib

    app_secret = (app_secret or "").strip()
    provided_signature = (provided_signature or "").strip()
    if not app_secret or not provided_signature:
        return False
    if not provided_signature.lower().startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided_signature.split("=", 1)[1], expected)
