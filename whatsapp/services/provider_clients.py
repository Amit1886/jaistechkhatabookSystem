from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse

from whatsapp.models import WhatsAppAccount
from whatsapp.providers.meta_cloud import MetaCloudWhatsAppClient
from whatsapp.providers.web_gateway import WebGatewayWhatsAppClient
from whatsapp.services.phone import normalize_wa_phone


@dataclass(frozen=True)
class OutboundResult:
    ok: bool
    status_code: int
    response_text: str
    provider: str
    provider_message_id: str = ""


def get_outbound_client(account: WhatsAppAccount):
    provider = (account.provider or "").strip().lower()
    if provider == WhatsAppAccount.Provider.META_CLOUD_API:
        return MetaCloudWhatsAppClient(
            phone_number_id=account.meta_phone_number_id,
            access_token=account.meta_access_token,
            graph_version=account.meta_graph_version or "v20.0",
        )
    if provider == WhatsAppAccount.Provider.WEB_GATEWAY:
        base = (getattr(settings, "BASE_URL", "") or "").rstrip("/")
        inbound_path = reverse("whatsapp_gateway_inbound_webhook", kwargs={"account_id": str(account.id)})
        webhook_url = (base + inbound_path) if base else ""
        return WebGatewayWhatsAppClient(
            base_url=account.gateway_base_url,
            api_key=account.gateway_api_key,
            session_id=account.gateway_session_id,
            webhook_url=webhook_url,
            webhook_secret=account.webhook_secret,
        )
    raise ValueError(f"Unsupported WhatsApp provider: {account.provider}")


def send_text(*, account: WhatsAppAccount, to: str, text: str) -> OutboundResult:
    provider = account.provider
    to_norm = normalize_wa_phone(to, default_country_code=str(getattr(settings, "WA_DEFAULT_COUNTRY_CODE", "") or ""))
    if not to_norm:
        return OutboundResult(ok=False, status_code=400, response_text="Missing/invalid to number", provider=provider)
    client = get_outbound_client(account)
    if isinstance(client, MetaCloudWhatsAppClient):
        res = client.send_text(to=to_norm, text=text)
        return OutboundResult(
            ok=res.ok,
            status_code=res.status_code,
            response_text=res.response_text,
            provider=provider,
            provider_message_id=res.message_id,
        )
    if isinstance(client, WebGatewayWhatsAppClient):
        res = client.send_text(to=to_norm, text=text)
        return OutboundResult(ok=res.ok, status_code=res.status_code, response_text=res.response_text, provider=provider)
    raise ValueError(f"Unsupported WhatsApp provider client for {provider}")


def send_document_link(*, account: WhatsAppAccount, to: str, link: str, filename: str = "invoice.pdf", caption: str = "") -> OutboundResult:
    provider = account.provider
    to_norm = normalize_wa_phone(to, default_country_code=str(getattr(settings, "WA_DEFAULT_COUNTRY_CODE", "") or ""))
    if not to_norm:
        return OutboundResult(ok=False, status_code=400, response_text="Missing/invalid to number", provider=provider)
    client = get_outbound_client(account)
    if isinstance(client, MetaCloudWhatsAppClient):
        res = client.send_document_link(to=to_norm, link=link, filename=filename, caption=caption)
        return OutboundResult(
            ok=res.ok,
            status_code=res.status_code,
            response_text=res.response_text,
            provider=provider,
            provider_message_id=res.message_id,
        )
    if isinstance(client, WebGatewayWhatsAppClient):
        # Most gateways need their own media-upload flow; fall back to sending the link.
        text = caption.strip() if caption else "Document"
        fallback = f"{text}: {link}".strip()
        res = client.send_text(to=to_norm, text=fallback)
        return OutboundResult(ok=res.ok, status_code=res.status_code, response_text=res.response_text, provider=provider)
    raise ValueError(f"Unsupported WhatsApp provider client for {provider}")


def send_image_link(*, account: WhatsAppAccount, to: str, link: str, caption: str = "") -> OutboundResult:
    provider = account.provider
    to_norm = normalize_wa_phone(to, default_country_code=str(getattr(settings, "WA_DEFAULT_COUNTRY_CODE", "") or ""))
    if not to_norm:
        return OutboundResult(ok=False, status_code=400, response_text="Missing/invalid to number", provider=provider)
    client = get_outbound_client(account)
    if isinstance(client, MetaCloudWhatsAppClient):
        res = client.send_image_link(to=to_norm, link=link, caption=caption)
        return OutboundResult(
            ok=res.ok,
            status_code=res.status_code,
            response_text=res.response_text,
            provider=provider,
            provider_message_id=res.message_id,
        )
    if isinstance(client, WebGatewayWhatsAppClient):
        text = caption.strip() if caption else "Image"
        fallback = f"{text}: {link}".strip()
        res = client.send_text(to=to_norm, text=fallback)
        return OutboundResult(ok=res.ok, status_code=res.status_code, response_text=res.response_text, provider=provider)
    raise ValueError(f"Unsupported WhatsApp provider client for {provider}")


def healthcheck(account: WhatsAppAccount) -> OutboundResult:
    provider = account.provider
    client = get_outbound_client(account)
    if isinstance(client, MetaCloudWhatsAppClient):
        res = client.healthcheck()
        return OutboundResult(ok=res.ok, status_code=res.status_code, response_text=res.response_text, provider=provider)
    if isinstance(client, WebGatewayWhatsAppClient):
        res = client.healthcheck()
        return OutboundResult(ok=res.ok, status_code=res.status_code, response_text=res.response_text, provider=provider)
    # Fallback
    return OutboundResult(ok=False, status_code=400, response_text="Unsupported provider client", provider=provider)
