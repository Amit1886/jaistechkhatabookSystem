from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from whatsapp.models import WhatsAppAccount
from whatsapp.services.phone import normalize_wa_phone


class Command(BaseCommand):
    help = "Create a demo WhatsApp Web-Gateway account + demo catalog + demo flow for an existing user."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="User identifier (email OR username OR id OR mobile).")
        parser.add_argument("--wa", required=True, help="WhatsApp number (10-digit ok, country code auto-applied).")
        parser.add_argument("--no-request-qr", action="store_true", help="Do not call the gateway to request QR.")

    def _find_user(self, ident: str):
        User = get_user_model()
        ident = (ident or "").strip()
        if not ident:
            return None

        # Try primary key
        if ident.isdigit():
            try:
                u = User.objects.filter(id=int(ident)).first()
                if u:
                    return u
            except Exception:
                pass

        # Try email / username exact
        u = User.objects.filter(email__iexact=ident).first()
        if u:
            return u
        u = User.objects.filter(username=ident).first()
        if u:
            return u

        # Try mobile last-10
        digits = "".join(ch for ch in ident if ch.isdigit())
        d10 = digits[-10:] if len(digits) > 10 else digits
        if d10:
            u = User.objects.filter(mobile__endswith=d10).first()
            if u:
                return u

        return None

    def handle(self, *args, **options):
        user_ident = str(options["user"])
        wa_raw = str(options["wa"])
        request_qr = not bool(options.get("no_request_qr"))

        user = self._find_user(user_ident)
        if not user:
            raise CommandError(f"User not found for: {user_ident}")

        default_cc = str(getattr(settings, "WA_DEFAULT_COUNTRY_CODE", "") or "").strip()
        wa = normalize_wa_phone(wa_raw, default_country_code=default_cc)
        if not wa:
            raise CommandError("Invalid --wa number")

        gateway_base_url = str(getattr(settings, "WA_GATEWAY_BASE_URL", "") or getattr(settings, "WHATSAPP_GATEWAY_BASE_URL", "") or "").strip()
        gateway_api_key = str(getattr(settings, "WA_GATEWAY_API_KEY", "") or getattr(settings, "WHATSAPP_GATEWAY_API_KEY", "") or "").strip()
        if not gateway_base_url:
            raise CommandError("WA_GATEWAY_BASE_URL is not configured in Django settings/.env")

        d10 = wa[-10:] if len(wa) > 10 else wa
        acc = WhatsAppAccount.objects.filter(owner=user, provider=WhatsAppAccount.Provider.WEB_GATEWAY, phone_number=wa).first()
        if not acc and d10:
            acc = (
                WhatsAppAccount.objects.filter(owner=user, provider=WhatsAppAccount.Provider.WEB_GATEWAY, phone_number__endswith=d10)
                .order_by("-updated_at", "-created_at")
                .first()
            )

        created = False
        if not acc:
            acc = WhatsAppAccount.objects.create(
                owner=user,
                label="WhatsApp (Demo)",
                phone_number=wa,
                provider=WhatsAppAccount.Provider.WEB_GATEWAY,
                status=WhatsAppAccount.Status.DISCONNECTED,
                gateway_base_url=gateway_base_url[:255],
                gateway_api_key=gateway_api_key,
                gateway_session_id=uuid.uuid4().hex,
            )
            created = True
        else:
            if wa and (acc.phone_number or "").strip() != wa:
                conflict = WhatsAppAccount.objects.filter(owner=user, phone_number=wa).exclude(id=acc.id).exists()
                if not conflict:
                    acc.phone_number = wa
            if gateway_base_url:
                acc.gateway_base_url = gateway_base_url[:255]
            if gateway_api_key:
                acc.gateway_api_key = gateway_api_key
            if not (acc.gateway_session_id or "").strip():
                acc.gateway_session_id = uuid.uuid4().hex
            if not (acc.label or "").strip():
                acc.label = "WhatsApp (Demo)"
            acc.save()

        # Seed demo catalog + flow (safe no-op if already present)
        try:
            from whatsapp.setup_views import _ensure_operator_for_user, _seed_demo_products

            _seed_demo_products(owner=user)
            _ensure_operator_for_user(owner=user, account=acc)
        except Exception as e:
            raise CommandError(f"Failed seeding demo products/operator: {e}")

        try:
            from whatsapp.visual_views import _create_demo_flow

            _create_demo_flow(owner=user, account=acc)
        except Exception as e:
            raise CommandError(f"Failed creating demo flow: {e}")

        qr_status = ""
        if request_qr:
            try:
                from whatsapp.setup_views import _request_qr_and_store_session

                ok, payload, is_connected = _request_qr_and_store_session(account=acc)
                if ok and is_connected:
                    qr_status = "connected"
                elif ok:
                    qr_status = "qr_required"
                else:
                    qr_status = f"qr_failed: {(payload or '')[:120]}"
            except Exception as e:
                qr_status = f"qr_failed: {e}"

        try:
            from django.urls import reverse

            wizard_path = reverse("whatsapp:setup_wizard")
        except Exception:
            wizard_path = "/ai-tools/whatsapp/setup/"

        base = str(getattr(settings, "BASE_URL", "") or "").rstrip("/")
        wizard_url = f"{base}{wizard_path}?account={acc.id}" if base else f"{wizard_path}?account={acc.id}"

        self.stdout.write(self.style.SUCCESS("WhatsApp demo ready."))
        self.stdout.write(f"user={getattr(user, 'email', '') or getattr(user, 'username', '') or user.id}")
        self.stdout.write(f"account_id={acc.id} created={created}")
        self.stdout.write(f"wa_number={acc.phone_number} session_id={acc.gateway_session_id}")
        self.stdout.write(f"gateway_base_url={acc.gateway_base_url}")
        if qr_status:
            self.stdout.write(f"qr_status={qr_status}")
        self.stdout.write(f"open_wizard={wizard_url}")

