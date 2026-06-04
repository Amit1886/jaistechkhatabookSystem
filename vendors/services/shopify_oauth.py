from __future__ import annotations

import hashlib
import hmac
import json
import re
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.core import signing


_SHOP_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


def _get_global_setting(key: str, default: Any = "") -> Any:
    try:
        from core_settings.models import SettingDefinition, SettingValue
        from core_settings.services import sync_settings_registry

        try:
            sync_settings_registry()
        except Exception:
            pass

        definition = SettingDefinition.objects.filter(key=key).first()
        if not definition:
            return default
        value_obj = SettingValue.objects.filter(definition=definition, owner__isnull=True).first()
        return value_obj.value if value_obj else definition.default_value
    except Exception:
        return default


def normalize_shop_domain(raw: str) -> str:
    v = (raw or "").strip().lower()
    v = v.replace("https://", "").replace("http://", "").strip().strip("/")
    return v


def is_valid_shop_domain(shop_domain: str) -> bool:
    return bool(_SHOP_RE.match(normalize_shop_domain(shop_domain)))


def get_shopify_client_id() -> str:
    return (
        str(_get_global_setting("shopify_client_id", "") or "").strip()
        or (getattr(settings, "SHOPIFY_CLIENT_ID", "") or "").strip()
    )


def get_shopify_client_secret() -> str:
    return (
        str(_get_global_setting("shopify_client_secret", "") or "").strip()
        or (getattr(settings, "SHOPIFY_CLIENT_SECRET", "") or "").strip()
    )


def get_shopify_scopes() -> str:
    # Comma-separated scopes as expected by Shopify authorize URL.
    return (
        str(_get_global_setting("shopify_scopes", "") or "").strip()
        or (getattr(settings, "SHOPIFY_SCOPES", "") or "").strip()
        or "read_orders,read_products,read_customers"
    ).strip()


def sign_oauth_state(payload: dict[str, Any], max_age_seconds: int = 15 * 60) -> str:
    signer = signing.TimestampSigner(salt="shopify-oauth-state")
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    token = signer.sign(raw)
    # max_age enforced on unsign; included here to keep call-sites explicit.
    return token


def unsign_oauth_state(token: str, max_age_seconds: int = 15 * 60) -> dict[str, Any] | None:
    signer = signing.TimestampSigner(salt="shopify-oauth-state")
    try:
        raw = signer.unsign(token, max_age=max_age_seconds)
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def build_authorize_url(*, shop_domain: str, redirect_uri: str, state: str) -> str:
    shop = normalize_shop_domain(shop_domain)
    client_id = get_shopify_client_id()
    scopes = get_shopify_scopes()
    params = {
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"https://{shop}/admin/oauth/authorize?{urllib.parse.urlencode(params)}"


def _build_hmac_message(params: dict[str, str]) -> str:
    pairs: list[str] = []
    for k in sorted(params.keys()):
        pairs.append(f"{k}={params[k]}")
    return "&".join(pairs)


def verify_shopify_hmac(query_params: dict[str, str]) -> bool:
    """
    Verify `hmac` query parameter from Shopify OAuth callback.
    """
    secret = get_shopify_client_secret()
    if not secret:
        return False

    hmac_in = (query_params.get("hmac") or "").strip()
    if not hmac_in:
        return False

    data = {k: v for k, v in query_params.items() if k != "hmac"}
    msg = _build_hmac_message(data)
    digest = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(digest, hmac_in)
    except Exception:
        return digest == hmac_in


def exchange_code_for_access_token(*, shop_domain: str, code: str) -> dict[str, Any]:
    """
    POST https://{shop}.myshopify.com/admin/oauth/access_token with
    client_id, client_secret, code.
    """
    shop = normalize_shop_domain(shop_domain)
    url = f"https://{shop}/admin/oauth/access_token"

    payload = urllib.parse.urlencode(
        {
            "client_id": get_shopify_client_id(),
            "client_secret": get_shopify_client_secret(),
            "code": (code or "").strip(),
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw or "{}")
        except Exception:
            return {"raw": raw}
