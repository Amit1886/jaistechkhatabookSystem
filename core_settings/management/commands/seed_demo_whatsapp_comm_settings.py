from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import apply_updates, sync_settings_registry


class Command(BaseCommand):
    help = "Seed demo values for WhatsApp & Communication settings (global scope)."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, default=None, help="Admin user id to mark as updated_by.")
        parser.add_argument("--email", type=str, default=None, help="Admin user email to mark as updated_by.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing values (otherwise only fills missing SettingValue rows).",
        )
        parser.add_argument("--dry-run", action="store_true", help="Print what would change without saving.")

    def _resolve_admin_user(self, *, user_id: int | None, email: str | None):
        User = get_user_model()
        if user_id:
            u = User.objects.filter(id=int(user_id)).first()
            if u:
                return u
        if email:
            u = User.objects.filter(email__iexact=str(email).strip()).first()
            if u:
                return u
        return User.objects.filter(is_superuser=True).order_by("id").first() or User.objects.filter(is_staff=True).order_by("id").first()

    def handle(self, *args, **opts):
        sync_settings_registry()

        admin_user = self._resolve_admin_user(user_id=opts.get("user_id"), email=opts.get("email"))
        if not admin_user:
            raise CommandError("No admin/staff user found. Create a superuser first, or pass --user-id/--email.")

        updates = [
            {
                "key": "whatsapp_api_config",
                "value": (
                    "DEMO CONFIG (UltraMsg)\n"
                    "- Provider: ultramsg\n"
                    "- Instance ID: instance123456\n"
                    "- Token: DEMO_ULTRAMSG_TOKEN\n"
                    "- Webhook secret: demo-wa-secret-1234\n\n"
                    "Note: Replace with real credentials to send messages."
                ),
            },
            {"key": "wa_enabled", "value": True},
            {"key": "wa_provider", "value": "ultramsg"},
            {"key": "wa_ultramsg_instance_id", "value": "instance123456"},
            {"key": "wa_ultramsg_token", "value": "DEMO_ULTRAMSG_TOKEN"},
            {"key": "wa_webhook_secret", "value": "demo-wa-secret-1234"},
            {"key": "order_via_whatsapp", "value": True},
            {"key": "invoice_share_auto", "value": True},
            {"key": "payment_link_auto", "value": True},
            {
                "key": "reminder_templates",
                "value": [
                    {
                        "name": "Payment Due",
                        "channel": "whatsapp",
                        "template": "Hi {party_name}, your outstanding due is ₹{due_amount}. Please pay by {due_date}.",
                    },
                    {
                        "name": "Invoice Shared",
                        "channel": "whatsapp",
                        "template": "Invoice {invoice_number} for ₹{invoice_amount} is shared. Thank you!",
                    },
                ],
            },
            {"key": "chatbot_order_mode", "value": True},
            {
                "key": "sms_gateway_config",
                "value": (
                    "{\n"
                    "  \"provider\": \"demo\",\n"
                    "  \"api_key\": \"DEMO_SMS_KEY\",\n"
                    "  \"sender_id\": \"JAISTC\"\n"
                    "}\n"
                ),
            },
            {
                "key": "email_smtp_config",
                "value": (
                    "host=smtp.example.com\n"
                    "port=587\n"
                    "username=demo@example.com\n"
                    "password=DEMO_SMTP_PASSWORD\n"
                    "use_tls=true\n"
                ),
            },
        ]

        if not bool(opts.get("force")):
            # Only fill settings that don't yet have a global SettingValue row.
            keep = []
            for u in updates:
                key = u.get("key")
                if not key:
                    continue
                definition = SettingDefinition.objects.filter(key=key).first()
                if not definition:
                    continue
                exists = SettingValue.objects.filter(definition=definition, owner__isnull=True).exists()
                if not exists:
                    keep.append(u)
            updates = keep

        if not updates:
            self.stdout.write(self.style.SUCCESS("Nothing to update (use --force to overwrite)."))
            return

        if bool(opts.get("dry_run")):
            self.stdout.write("Dry-run. Would apply updates:")
            for u in updates:
                self.stdout.write(f"- {u['key']}")
            return

        results = apply_updates(admin_user, updates)
        updated = [r for r in results if r.get("status") == "updated"]
        self.stdout.write(self.style.SUCCESS(f"Applied demo settings: {len(updated)} updated."))

