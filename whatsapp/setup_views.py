from __future__ import annotations

import json
import secrets
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from whatsapp.models import WhatsAppAccount, WhatsAppMessage, WhatsAppOperator, WhatsAppSession
from whatsapp.services.friendly_errors import friendly_error
from whatsapp.services.phone import normalize_wa_phone
from whatsapp.services.gateway_autostart import restart_local_gateway


def _default_gateway_base_url() -> str:
    return str(getattr(settings, "WA_GATEWAY_BASE_URL", "") or getattr(settings, "WHATSAPP_GATEWAY_BASE_URL", "") or "")


def _default_gateway_api_key() -> str:
    return str(getattr(settings, "WA_GATEWAY_API_KEY", "") or getattr(settings, "WHATSAPP_GATEWAY_API_KEY", "") or "")


def _default_country_code() -> str:
    return str(getattr(settings, "WA_DEFAULT_COUNTRY_CODE", "") or "")


def _seed_demo_products(*, owner) -> None:
    """
    Seed a minimal demo catalog so 'products' works immediately for new users.
    Safe: only seeds when the owner has zero products.
    """
    try:
        from decimal import Decimal

        from commerce.models import Category, Product

        if Product.objects.filter(owner=owner).exists():
            return

        grocery = Category.objects.create(owner=owner, name="Grocery", description="Demo category")
        dairy = Category.objects.create(owner=owner, name="Dairy", description="Demo category")

        def _sku() -> str:
            return ("DEMO-" + secrets.token_hex(5)).upper()

        Product.objects.bulk_create(
            [
                Product(owner=owner, category=grocery, name="Rice", price=Decimal("55.00"), stock=120, min_stock=10, sku=_sku(), unit="kg"),
                Product(owner=owner, category=grocery, name="Sugar", price=Decimal("45.00"), stock=80, min_stock=10, sku=_sku(), unit="kg"),
                Product(owner=owner, category=grocery, name="Wheat Flour", price=Decimal("42.00"), stock=70, min_stock=10, sku=_sku(), unit="kg"),
                Product(owner=owner, category=dairy, name="Milk", price=Decimal("30.00"), stock=50, min_stock=10, sku=_sku(), unit="ltr"),
            ]
        )
    except Exception:
        # Demo seeding should never break setup.
        return


def _ensure_operator_for_user(*, owner, account: WhatsAppAccount) -> None:
    """
    Allow the logged-in user mobile (or provided WhatsApp number) to run admin/report commands via WhatsApp.
    """
    try:
        raw = str(getattr(owner, "mobile", "") or "").strip() or (account.phone_number or "")
        phone = normalize_wa_phone(raw, default_country_code=_default_country_code())
        if not phone:
            return
        WhatsAppOperator.objects.get_or_create(
            owner=owner,
            whatsapp_account=account,
            phone_number=phone,
            defaults={"display_name": (getattr(owner, "username", "") or getattr(owner, "email", "") or "")[:120], "role": WhatsAppOperator.Role.ADMIN},
        )
    except Exception:
        return


def _request_qr_and_store_session(*, account: WhatsAppAccount) -> tuple[bool, str, bool]:
    """
    Returns (ok, payload, is_connected)
    """
    from whatsapp.services.provider_clients import get_outbound_client
    from whatsapp.services.gateway_autostart import restart_local_gateway

    client = get_outbound_client(account)

    # Best-effort: if local gateway is likely down, try to start it before requesting QR.
    try:
        if account.gateway_base_url and account.gateway_base_url.startswith(("http://127.0.0.1", "http://localhost")):
            restart_local_gateway()
    except Exception:
        pass

    res = client.request_qr()  # type: ignore[attr-defined]
    payload = (res.response_text or "").strip()
    parsed_qr = ""
    try:
        j = json.loads(payload)
        if isinstance(j, dict) and str(j.get("qr") or "").startswith("data:image"):
            parsed_qr = str(j.get("qr"))
    except Exception:
        pass

    # If gateway said unreachable, retry once after restart.
    if (not res.ok) and (payload.startswith("gateway_unreachable") or res.status_code == 503):
        try:
            restart_local_gateway()
        except Exception:
            pass
        res = client.request_qr()  # type: ignore[attr-defined]
        payload = (res.response_text or "").strip()
        try:
            j = json.loads(payload)
            if isinstance(j, dict) and str(j.get("qr") or "").startswith("data:image"):
                parsed_qr = str(j.get("qr"))
        except Exception:
            pass

    is_connected = bool(res.ok) and payload.lower() == "connected"

    sess = WhatsAppSession.objects.filter(account=account).order_by("-updated_at").first()
    if not sess:
        sess = WhatsAppSession.objects.create(account=account)

    sess.status = (
        WhatsAppSession.Status.CONNECTED
        if is_connected
        else (WhatsAppSession.Status.QR_REQUIRED if res.ok else WhatsAppSession.Status.ERROR)
    )
    sess.qr_payload = "" if is_connected else (parsed_qr or payload)
    sess.last_qr_at = timezone.now()
    sess.last_connected_at = timezone.now() if is_connected else sess.last_connected_at
    sess.last_error = "" if res.ok else payload[:2000]
    sess.save(update_fields=["status", "qr_payload", "last_qr_at", "last_connected_at", "last_error", "updated_at"])

    account.status = (
        WhatsAppAccount.Status.CONNECTED
        if is_connected
        else (WhatsAppAccount.Status.CONNECTING if res.ok else WhatsAppAccount.Status.ERROR)
    )
    account.save(update_fields=["status", "updated_at"])
    return bool(res.ok), payload, is_connected


@login_required
def whatsapp_setup_wizard(request):
    """
    Smart step-by-step setup for user WhatsApp connection.

    Supports:
    - WhatsApp Cloud API (Official) token setup
    - Web Gateway (QR) setup (gateway service generates QR)
    """
    accounts = list(WhatsAppAccount.objects.filter(owner=request.user).order_by("-updated_at", "-created_at")[:50])
    selected = None
    selected_id = (request.GET.get("account") or "").strip()
    if selected_id:
        selected = get_object_or_404(WhatsAppAccount, id=selected_id, owner=request.user)
    elif accounts:
        selected = accounts[0]

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "start_local_gateway":
            try:
                started = restart_local_gateway()
                if started:
                    messages.success(request, "Local gateway start triggered. Refresh QR in a moment.")
                else:
                    messages.info(request, "Gateway not started. Ensure Node + whatsapp_gateway are installed.")
            except Exception:
                messages.error(request, "Could not start local gateway.")
            return redirect(reverse("whatsapp:setup_wizard") + (f"?account={selected.id}" if selected else ""))

        if action == "quick_demo_setup":
            raw_phone = (request.POST.get("quick_phone_number") or "").strip()[:32]
            if not raw_phone:
                # Use a sensible fallback so users aren't blocked by an empty field
                raw_phone = (getattr(request.user, "mobile", "") or "9555733478")
            phone_number = normalize_wa_phone(raw_phone, default_country_code=_default_country_code())
            if not phone_number:
                messages.error(request, "WhatsApp number is required.")
                return redirect(reverse("whatsapp:setup_wizard"))

            gateway_base_url = (_default_gateway_base_url() or "").strip()[:255]
            gateway_api_key = (_default_gateway_api_key() or "").strip()
            if not gateway_base_url:
                messages.error(request, "Gateway Base URL is not set. Ask admin or set WA_GATEWAY_BASE_URL in .env.")
                return redirect(reverse("whatsapp:setup_wizard"))

            with transaction.atomic():
                d10 = phone_number[-10:] if len(phone_number) > 10 else phone_number
                acc = WhatsAppAccount.objects.filter(
                    owner=request.user,
                    provider=WhatsAppAccount.Provider.WEB_GATEWAY,
                    phone_number=phone_number,
                ).first()
                if not acc and d10:
                    acc = (
                        WhatsAppAccount.objects.filter(
                            owner=request.user,
                            provider=WhatsAppAccount.Provider.WEB_GATEWAY,
                            phone_number__endswith=d10,
                        )
                        .order_by("-updated_at", "-created_at")
                        .first()
                    )
                if not acc:
                    acc = WhatsAppAccount.objects.create(
                        owner=request.user,
                        label="WhatsApp (Demo)",
                        phone_number=phone_number,
                        provider=WhatsAppAccount.Provider.WEB_GATEWAY,
                        status=WhatsAppAccount.Status.DISCONNECTED,
                        gateway_base_url=gateway_base_url,
                        gateway_session_id=uuid.uuid4().hex,
                    )
                # Keep the demo experience reliable: sync gateway details from settings.
                if gateway_base_url:
                    acc.gateway_base_url = gateway_base_url
                if gateway_api_key:
                    acc.gateway_api_key = gateway_api_key
                elif _default_gateway_api_key():
                    acc.gateway_api_key = _default_gateway_api_key()
                if not (acc.gateway_session_id or "").strip():
                    acc.gateway_session_id = uuid.uuid4().hex
                if phone_number and (acc.phone_number or "").strip() != phone_number:
                    # Only update if it won't violate the unique constraint.
                    conflict = (
                        WhatsAppAccount.objects.filter(owner=request.user, phone_number=phone_number)
                        .exclude(id=acc.id)
                        .exists()
                    )
                    if not conflict:
                        acc.phone_number = phone_number
                if not (acc.label or "").strip():
                    acc.label = "WhatsApp (Demo)"
                acc.save()

                # If using local gateway, try to start it automatically
                if acc.gateway_base_url and acc.gateway_base_url.startswith(("http://127.0.0.1", "http://localhost")):
                    try:
                        restart_local_gateway()
                    except Exception:
                        pass

                _seed_demo_products(owner=request.user)
                _ensure_operator_for_user(owner=request.user, account=acc)

                try:
                    from whatsapp.visual_views import _create_demo_flow  # type: ignore

                    _create_demo_flow(owner=request.user, account=acc)
                except Exception:
                    pass

                ok, payload, is_connected = _request_qr_and_store_session(account=acc)

            if ok:
                messages.success(request, "Demo setup created. Scan QR to connect." if not is_connected else "Demo setup ready (already connected).")
            else:
                messages.warning(request, f"Demo created but QR request failed: {friendly_error(payload or 'error')[:220]}. Start the local gateway or use Cloud API.")
            return redirect(reverse("whatsapp:setup_wizard") + f"?account={acc.id}")

        if action == "create_account":
            provider = (request.POST.get("provider") or WhatsAppAccount.Provider.WEB_GATEWAY).strip()
            label = (request.POST.get("label") or "").strip()[:120]
            phone_number_raw = (request.POST.get("phone_number") or "").strip()[:32]
            phone_number = normalize_wa_phone(phone_number_raw, default_country_code=_default_country_code())

            meta_phone_number_id = (request.POST.get("meta_phone_number_id") or "").strip()[:64]
            meta_waba_id = (request.POST.get("meta_waba_id") or "").strip()[:64]
            meta_graph_version = (request.POST.get("meta_graph_version") or "v20.0").strip()[:16] or "v20.0"
            meta_access_token = (request.POST.get("meta_access_token") or "").strip()
            meta_app_secret = (request.POST.get("meta_app_secret") or "").strip()

            gateway_base_url = (request.POST.get("gateway_base_url") or "").strip()[:255] or (_default_gateway_base_url() or "").strip()[:255]
            gateway_api_key = (request.POST.get("gateway_api_key") or "").strip() or (_default_gateway_api_key() or "").strip()
            gateway_session_id = (request.POST.get("gateway_session_id") or "").strip()[:120]
            if provider == WhatsAppAccount.Provider.WEB_GATEWAY and not gateway_session_id:
                gateway_session_id = uuid.uuid4().hex

            try:
                acc = WhatsAppAccount.objects.create(
                    owner=request.user,
                    label=label,
                    phone_number=phone_number or phone_number_raw,
                    provider=provider,
                    status=WhatsAppAccount.Status.DISCONNECTED,
                    meta_phone_number_id=meta_phone_number_id,
                    meta_waba_id=meta_waba_id,
                    meta_graph_version=meta_graph_version,
                    gateway_base_url=gateway_base_url,
                    gateway_session_id=gateway_session_id,
                )
                if meta_access_token:
                    acc.meta_access_token = meta_access_token
                if meta_app_secret:
                    acc.meta_app_secret = meta_app_secret
                if gateway_api_key:
                    acc.gateway_api_key = gateway_api_key
                acc.save()
                _ensure_operator_for_user(owner=request.user, account=acc)
                messages.success(request, "WhatsApp account added. Continue setup below.")
                return redirect(reverse("whatsapp:setup_wizard") + f"?account={acc.id}")
            except Exception:
                messages.error(request, "Failed to add WhatsApp account. Check details / duplicates.")
                return redirect(reverse("whatsapp:setup_wizard"))

        if action == "update_account" and selected:
            try:
                if selected.provider == WhatsAppAccount.Provider.META_CLOUD_API:
                    selected.meta_phone_number_id = (request.POST.get("meta_phone_number_id") or "").strip()[:64]
                    selected.meta_waba_id = (request.POST.get("meta_waba_id") or "").strip()[:64]
                    selected.meta_graph_version = (request.POST.get("meta_graph_version") or "v20.0").strip()[:16] or "v20.0"
                    token = (request.POST.get("meta_access_token") or "").strip()
                    secret = (request.POST.get("meta_app_secret") or "").strip()
                    if token:
                        selected.meta_access_token = token
                    if secret:
                        selected.meta_app_secret = secret

                if selected.provider == WhatsAppAccount.Provider.WEB_GATEWAY:
                    selected.gateway_base_url = (request.POST.get("gateway_base_url") or "").strip()[:255] or (_default_gateway_base_url() or "").strip()[:255]
                    api_key = (request.POST.get("gateway_api_key") or "").strip()
                    sess = (request.POST.get("gateway_session_id") or "").strip()[:120]
                    if api_key:
                        selected.gateway_api_key = api_key
                    if sess:
                        selected.gateway_session_id = sess
                    if not (selected.gateway_session_id or "").strip():
                        selected.gateway_session_id = uuid.uuid4().hex
                    if not (selected.gateway_api_key or "").strip():
                        selected.gateway_api_key = (_default_gateway_api_key() or "").strip()

                selected.save()
                _ensure_operator_for_user(owner=request.user, account=selected)
                messages.success(request, "Settings saved.")
            except Exception:
                messages.error(request, "Failed to save settings.")
            return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")

        if action == "request_qr" and selected:
            if selected.provider != WhatsAppAccount.Provider.WEB_GATEWAY:
                messages.error(request, "QR is supported only for Web Gateway accounts.")
                return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")
            try:
                if not (selected.gateway_session_id or "").strip():
                    selected.gateway_session_id = uuid.uuid4().hex
                    selected.save(update_fields=["gateway_session_id", "updated_at"])

                ok, payload, is_connected = _request_qr_and_store_session(account=selected)
                if ok:
                    messages.success(
                        request,
                        "Already connected."
                        if is_connected
                        else "QR requested. Scan it from WhatsApp Business App > Linked devices.",
                    )
                else:
                    err = friendly_error(payload or "qr_request_failed")
                    messages.error(request, f"QR request failed: {err[:220]}")
            except Exception:
                messages.error(request, "Failed to request QR. Check gateway settings.")
            return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")

        if action == "reconnect" and selected:
            if selected.provider != WhatsAppAccount.Provider.WEB_GATEWAY:
                messages.error(request, "Reconnect is supported only for Web Gateway accounts.")
                return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")
            try:
                if not (selected.gateway_session_id or "").strip():
                    selected.gateway_session_id = uuid.uuid4().hex
                    selected.save(update_fields=["gateway_session_id", "updated_at"])

                # For QR gateways, reconnecting and requesting QR are effectively the same operation.
                ok, payload, is_connected = _request_qr_and_store_session(account=selected)
                if ok:
                    messages.success(
                        request,
                        "Connected."
                        if is_connected
                        else "Reconnect started. Scan the latest QR (auto-refresh enabled).",
                    )
                else:
                    err = friendly_error(payload or "reconnect_failed")
                    messages.error(request, f"Reconnect failed: {err[:220]}")
            except Exception:
                messages.error(request, "Failed to reconnect. Check gateway settings.")
            return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")

        if action == "send_test" and selected:
            to_raw = (request.POST.get("test_to_number") or "").strip()
            text = (request.POST.get("test_message_text") or "").strip() or "Hello! WhatsApp setup test message."
            if not to_raw:
                messages.error(request, "Test To number is required.")
                return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")
            try:
                from whatsapp.services.provider_clients import send_text as send_text_out

                to = normalize_wa_phone(to_raw, default_country_code=_default_country_code())
                res = send_text_out(account=selected, to=to, text=text)
                WhatsAppMessage.objects.create(
                    owner=request.user,
                    whatsapp_account=selected,
                    direction=WhatsAppMessage.Direction.OUTBOUND,
                    from_number=(selected.phone_number or "").strip(),
                    to_number=to or to_raw,
                    body=text,
                    message_type="text",
                    provider_message_id=res.provider_message_id,
                    raw_payload={"provider": res.provider, "status_code": res.status_code, "response": (res.response_text or "")[:5000]},
                    status=WhatsAppMessage.Status.PROCESSED if res.ok else WhatsAppMessage.Status.FAILED,
                    error="" if res.ok else (res.response_text or "")[:2000],
                    parsed_intent="setup_test",
                )
                if res.ok:
                    messages.success(request, f"Test message sent to {to or to_raw}.")
                else:
                    err = friendly_error(res.response_text or "send_failed")
                    messages.error(request, f"Test failed: {err[:220]}")
            except Exception:
                messages.error(request, "Failed to send test message.")
            return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")

        if action == "healthcheck" and selected:
            try:
                from whatsapp.services.provider_clients import healthcheck

                res = healthcheck(selected)
                if selected.provider == WhatsAppAccount.Provider.META_CLOUD_API:
                    selected.status = WhatsAppAccount.Status.CONNECTED if res.ok else WhatsAppAccount.Status.ERROR
                    selected.save(update_fields=["status", "updated_at"])
                if res.ok:
                    messages.success(request, "Healthcheck OK.")
                else:
                    err = friendly_error(res.response_text or "healthcheck_failed")
                    messages.error(request, f"Healthcheck failed: {err[:220]}")
            except Exception:
                messages.error(request, "Healthcheck failed.")
            return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")

        if action == "restart_gateway_service" and selected:
            if selected.provider != WhatsAppAccount.Provider.WEB_GATEWAY:
                messages.error(request, "Gateway restart is supported only for Web Gateway accounts.")
                return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")
            try:
                from whatsapp.services.gateway_autostart import restart_local_gateway

                ok = restart_local_gateway()
                if ok:
                    messages.success(request, "Gateway restart triggered. Wait 5-10 seconds, then Request QR again.")
                else:
                    messages.error(request, "Gateway restart not available (non-local gateway or permission issue).")
            except Exception:
                messages.error(request, "Gateway restart failed.")
            return redirect(reverse("whatsapp:setup_wizard") + f"?account={selected.id}")

        messages.error(request, "Invalid action.")
        return redirect(reverse("whatsapp:setup_wizard") + (f"?account={selected.id}" if selected else ""))

    # Computed URLs + session data
    meta_webhook_url = ""
    gateway_webhook_url = ""
    latest_session = None
    latest_qr_payload = ""
    if selected:
        meta_webhook_url = request.build_absolute_uri(reverse("whatsapp_meta_webhook", kwargs={"account_id": str(selected.id)}))
        gateway_webhook_url = request.build_absolute_uri(
            reverse("whatsapp_gateway_inbound_webhook", kwargs={"account_id": str(selected.id)})
        )
        latest_session = WhatsAppSession.objects.filter(account=selected).order_by("-updated_at").first()
        if latest_session and latest_session.qr_payload:
            qp = latest_session.qr_payload
            try:
                j = json.loads(qp)
                if isinstance(j, dict) and str(j.get("qr") or "").startswith("data:image"):
                    latest_qr_payload = str(j.get("qr"))
                else:
                    latest_qr_payload = qp
            except Exception:
                latest_qr_payload = qp

    return render(
        request,
        "whatsapp/setup_wizard.html",
        {
            "accounts": accounts,
            "selected": selected,
            "meta_webhook_url": meta_webhook_url,
            "gateway_webhook_url": gateway_webhook_url,
            "latest_session": latest_session,
            "latest_qr_payload": latest_qr_payload,
            "default_gateway_base_url": _default_gateway_base_url(),
            "default_gateway_api_key": _default_gateway_api_key(),
            "quick_demo_default_number": ((selected.phone_number or "").strip() if selected else "")
            or (getattr(request.user, "mobile", "") or "").strip()
            or "9555733478",
        },
    )


def _map_gateway_status_to_models(*, gateway_status: str, is_ready: bool, has_qr: bool, ok: bool) -> tuple[str, str]:
    if not ok:
        return WhatsAppSession.Status.ERROR, WhatsAppAccount.Status.ERROR

    st = (gateway_status or "").strip().lower()
    if is_ready or st == "ready":
        return WhatsAppSession.Status.CONNECTED, WhatsAppAccount.Status.CONNECTED

    if st in {"qr", "new", "initializing"}:
        return (
            WhatsAppSession.Status.QR_REQUIRED if has_qr or st == "qr" else WhatsAppSession.Status.NEW,
            WhatsAppAccount.Status.CONNECTING,
        )

    if st in {"disconnected", "logged_out"}:
        return WhatsAppSession.Status.DISCONNECTED, WhatsAppAccount.Status.DISCONNECTED

    if st in {"auth_failure", "error"}:
        return WhatsAppSession.Status.ERROR, WhatsAppAccount.Status.ERROR

    return WhatsAppSession.Status.NEW, WhatsAppAccount.Status.CONNECTING


@login_required
def whatsapp_setup_poll(request):
    """
    JSON poll endpoint used by the setup wizard for:
    - live connection indicator
    - QR auto-refresh (every 5 seconds)

    Query:
      ?account=<uuid>
    """

    account_id = (request.GET.get("account") or "").strip()
    if not account_id:
        return JsonResponse({"ok": False, "error": "missing_account"}, status=400)

    account = get_object_or_404(WhatsAppAccount, id=account_id, owner=request.user)

    if account.provider != WhatsAppAccount.Provider.WEB_GATEWAY:
        return JsonResponse({"ok": True, "provider": account.provider, "account_status": account.status})

    from whatsapp.services.provider_clients import get_outbound_client
    from whatsapp.providers.web_gateway import WebGatewayWhatsAppClient

    # Ensure gateway creds/base_url/session are present
    updated = []
    if not (account.gateway_base_url or "").strip():
        account.gateway_base_url = _default_gateway_base_url()
        updated.append("gateway_base_url")
    if not (account.gateway_api_key or "").strip():
        account.gateway_api_key = _default_gateway_api_key()
        updated.append("gateway_api_key")
    if not (account.gateway_session_id or "").strip():
        account.gateway_session_id = uuid.uuid4().hex
        updated.append("gateway_session_id")
    if updated:
        account.save(update_fields=updated + ["updated_at"])

    client = get_outbound_client(account)
    if not isinstance(client, WebGatewayWhatsAppClient):
        return JsonResponse({"ok": False, "error": "unsupported_provider"}, status=400)

    gateway_status = ""
    is_ready = False
    qr_image = ""
    qr_text = ""
    last_qr_at = None
    gateway_last_error = ""
    ok = False
    err = ""

    # 1) Try lightweight status endpoint first (fast, no waiting)
    st_res = client.get_status()
    ok = bool(st_res.ok)
    if st_res.ok:
        try:
            payload = json.loads(st_res.response_text or "{}")
        except Exception:
            payload = {}
        gateway_status = str(payload.get("status") or "")
        is_ready = bool(payload.get("is_ready") or False) or (str(payload.get("status") or "").strip().lower() == "ready")
        gateway_last_error = str(payload.get("last_error") or "")
        qr_image = str(payload.get("qr_image") or "")
        qr_text = str(payload.get("qr") or "")
        if (not qr_image) and payload.get("qr") and str(payload.get("qr")).startswith("data:image"):
            qr_image = str(payload.get("qr"))
        last_qr_at = payload.get("last_qr_at")
    else:
        # If unreachable, attempt to auto-start the local gateway once (best effort).
        try:
            from whatsapp.services.gateway_autostart import restart_local_gateway

            restart_local_gateway()
        except Exception:
            pass
        # If the gateway is unreachable, surface a friendly message and avoid spamming QR requests.
        if (st_res.status_code == 503) or (st_res.response_text or "").startswith("gateway_unreachable"):
            err = f"Gateway not reachable at {client.base_url or '127.0.0.1:3100'}"
        else:
            err = st_res.response_text or "gateway_offline"
        return JsonResponse(
            {
                "ok": False,
                "error": friendly_error(err),
                "provider": account.provider,
                "account_status": account.status,
                "session_status": account.status,
                "gateway_status": "offline",
                "is_connected": False,
                "qr_payload": "",
                "last_error": err[:400],
                "last_qr_at": None,
            }
        )

    # 2) Always fetch a fresh QR (even if gateway says ready).
    qr_res = client.request_qr(timeout_ms=12000)
    if qr_res.ok:
        ok = True
        out = (qr_res.response_text or "").strip()
        if out.lower() == "connected":
            gateway_status = "ready"
            is_ready = True
            qr_image = ""
            qr_text = ""
        else:
            gateway_status = gateway_status or "qr"
            if out.startswith("data:image"):
                qr_image = out
                qr_text = ""
            else:
                try:
                    parsed = json.loads(out)
                    if isinstance(parsed, dict) and str(parsed.get("qr") or "").startswith("data:image"):
                        qr_image = parsed.get("qr")
                        qr_text = ""
                    else:
                        qr_text = parsed.get("qr", out)
                except Exception:
                    qr_text = out
    else:
        ok = False
        err = qr_res.response_text or err or "qr_request_failed"

    has_qr = bool((qr_image or "").startswith("data:image") or (qr_text or "").strip())
    sess_status, acc_status = _map_gateway_status_to_models(
        gateway_status=gateway_status,
        is_ready=is_ready,
        has_qr=has_qr,
        ok=ok,
    )

    # Persist a snapshot for UI + debugging (avoid writing if unchanged).
    qr_payload = "" if sess_status == WhatsAppSession.Status.CONNECTED else (qr_image or qr_text or "")
    sess = WhatsAppSession.objects.filter(account=account).order_by("-updated_at").first()
    if not sess:
        sess = WhatsAppSession.objects.create(account=account)

    update_fields: list[str] = []
    now = timezone.now()

    qr_payload_changed = (sess.qr_payload or "") != (qr_payload or "")

    if sess.status != sess_status:
        sess.status = sess_status
        update_fields.append("status")
    if qr_payload_changed:
        sess.qr_payload = qr_payload or ""
        update_fields.append("qr_payload")
    if sess_status == WhatsAppSession.Status.CONNECTED and not sess.last_connected_at:
        sess.last_connected_at = now
        update_fields.append("last_connected_at")
    if has_qr and (qr_payload_changed or not sess.last_qr_at):
        # Update last_qr_at when QR is first shown or refreshed.
        sess.last_qr_at = now
        update_fields.append("last_qr_at")
    if not ok:
        new_err = (err or "")[:2000]
        if (sess.last_error or "") != new_err:
            sess.last_error = new_err
            update_fields.append("last_error")
    else:
        # Keep gateway error (if any) visible even when HTTP OK.
        new_err = (gateway_last_error or "")[:2000]
        if (sess.last_error or "") != new_err:
            sess.last_error = new_err
            update_fields.append("last_error")

    old_meta = dict(sess.meta or {})
    meta = dict(old_meta)
    if meta.get("gateway_status") != (gateway_status or ""):
        meta["gateway_status"] = gateway_status or ""
    if last_qr_at is not None:
        meta["gateway_last_qr_at"] = last_qr_at
    if meta != old_meta:
        sess.meta = meta
        update_fields.append("meta")

    if update_fields:
        sess.save(update_fields=update_fields + ["updated_at"])

    if account.status != acc_status:
        account.status = acc_status
        account.save(update_fields=["status", "updated_at"])

    return JsonResponse(
        {
            "ok": ok,
            "error": (friendly_error(err)[:240] if (not ok and err) else ""),
            "provider": account.provider,
            "account_status": account.status,
            "session_status": sess.status,
            "gateway_status": gateway_status or "",
            "is_connected": bool(sess.status == WhatsAppSession.Status.CONNECTED),
            "qr_payload": qr_payload or "",
            "last_error": (sess.last_error or "")[:400],
            "last_qr_at": (sess.last_qr_at.isoformat() if sess.last_qr_at else None),
        }
    )
