from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import requests
from requests import exceptions as req_exc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatewayResult:
    ok: bool
    status_code: int
    response_text: str


class WebGatewayWhatsAppClient:
    """
    Optional connector for QR-based WhatsApp Web / device gateways.

    IMPORTANT:
    Automating WhatsApp Web / the WhatsApp Business App via non-official clients may violate WhatsApp terms.
    Use the official WhatsApp Business Platform (Cloud API) whenever possible.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        session_id: str = "",
        webhook_url: str = "",
        webhook_secret: str = "",
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = (api_key or "").strip()
        self.session_id = (session_id or "").strip()
        # Optional: when requesting QR, configure gateway -> Django inbound webhook.
        self.webhook_url = (webhook_url or "").strip()
        self.webhook_secret = (webhook_secret or "").strip()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def request_qr(self, *, timeout_ms: int = 25000) -> GatewayResult:
        if not self.base_url:
            return GatewayResult(ok=False, status_code=400, response_text="Gateway base_url not set")
        url = f"{self.base_url}/sessions/qr"
        payload: dict[str, Any] = {"session_id": self.session_id} if self.session_id else {}
        # Ask the gateway to block until the QR is actually generated (most gateways support this flag).
        payload["wait_for_qr"] = True
        if self.webhook_url:
            payload["webhook_url"] = self.webhook_url
        if self.webhook_secret:
            payload["webhook_secret"] = self.webhook_secret
        payload["timeout_ms"] = int(timeout_ms or 25000)
        try:
            # Gateway responds within timeout_ms; keep HTTP timeout close so Django never hangs too long.
            http_timeout = max(12.0, (float(timeout_ms or 25000) / 1000.0) + 10.0)
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=http_timeout)
            return GatewayResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text)
        except req_exc.ConnectionError as e:
            logger.warning("Gateway request_qr unreachable at %s: %s", url, e)
            return GatewayResult(ok=False, status_code=503, response_text="gateway_unreachable")
        except Exception as e:
            logger.exception("Gateway request_qr failed")
            return GatewayResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")

    def send_text(self, *, to: str, text: str) -> GatewayResult:
        if not self.base_url:
            return GatewayResult(ok=False, status_code=400, response_text="Gateway base_url not set")
        url = f"{self.base_url}/messages/text"
        payload = {"to": (to or "").strip(), "text": (text or "").strip(), "session_id": self.session_id}
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=20)
            return GatewayResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text)
        except req_exc.ConnectionError as e:
            logger.warning("Gateway send_text unreachable at %s: %s", url, e)
            return GatewayResult(ok=False, status_code=503, response_text="gateway_unreachable")
        except Exception as e:
            logger.exception("Gateway send_text failed")
            return GatewayResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")

    def healthcheck(self) -> GatewayResult:
        if not self.base_url:
            return GatewayResult(ok=False, status_code=400, response_text="Gateway base_url not set")
        url = f"{self.base_url}/health"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            return GatewayResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text)
        except req_exc.ConnectionError as e:
            logger.warning("Gateway healthcheck unreachable at %s: %s", url, e)
            return GatewayResult(ok=False, status_code=503, response_text="gateway_unreachable")
        except Exception as e:
            logger.exception("Gateway healthcheck failed")
            return GatewayResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")

    def get_status(self) -> GatewayResult:
        if not self.base_url:
            return GatewayResult(ok=False, status_code=400, response_text="Gateway base_url not set")
        url = f"{self.base_url}/sessions/status"
        params: dict[str, Any] = {"session_id": self.session_id} if self.session_id else {}
        if self.webhook_url:
            params["webhook_url"] = self.webhook_url
        if self.webhook_secret:
            params["webhook_secret"] = self.webhook_secret
        try:
            resp = requests.get(url, params=params, headers=self._headers(), timeout=15)
            return GatewayResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text)
        except req_exc.ConnectionError as e:
            logger.warning("Gateway get_status unreachable at %s: %s", url, e)
            return GatewayResult(ok=False, status_code=503, response_text="gateway_unreachable")
        except Exception as e:
            logger.exception("Gateway get_status failed")
            return GatewayResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")

    def reconnect(self, *, wait_for_qr: bool = False, timeout_ms: int = 15000) -> GatewayResult:
        if not self.base_url:
            return GatewayResult(ok=False, status_code=400, response_text="Gateway base_url not set")
        url = f"{self.base_url}/sessions/reconnect"
        payload: dict[str, Any] = {"session_id": self.session_id} if self.session_id else {}
        if self.webhook_url:
            payload["webhook_url"] = self.webhook_url
        if self.webhook_secret:
            payload["webhook_secret"] = self.webhook_secret
        payload["wait_for_qr"] = bool(wait_for_qr)
        payload["timeout_ms"] = int(timeout_ms or 15000)
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=40)
            return GatewayResult(ok=resp.ok, status_code=resp.status_code, response_text=resp.text)
        except req_exc.ConnectionError as e:
            logger.warning("Gateway reconnect unreachable at %s: %s", url, e)
            return GatewayResult(ok=False, status_code=503, response_text="gateway_unreachable")
        except Exception as e:
            logger.exception("Gateway reconnect failed")
            return GatewayResult(ok=False, status_code=0, response_text=f"{type(e).__name__}: {e}")
