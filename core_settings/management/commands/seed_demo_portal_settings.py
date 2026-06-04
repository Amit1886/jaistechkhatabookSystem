from __future__ import annotations

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from core_settings.models import SettingDefinition, SettingValue
from core_settings.services import apply_updates, sync_settings_registry


class Command(BaseCommand):
    help = "Seed demo values for Customer & Supplier Portal settings (global scope)."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, default=None, help="Admin user id to mark as updated_by.")
        parser.add_argument("--email", type=str, default=None, help="Admin user email to mark as updated_by.")
        parser.add_argument(
            "--base-url",
            type=str,
            default=None,
            help="Portal Base URL. Defaults to Django BASE_URL.",
        )
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
        return (
            User.objects.filter(is_superuser=True).order_by("id").first()
            or User.objects.filter(is_staff=True).order_by("id").first()
        )

    def handle(self, *args, **opts):
        sync_settings_registry()

        admin_user = self._resolve_admin_user(user_id=opts.get("user_id"), email=opts.get("email"))
        if not admin_user:
            raise CommandError("No admin/staff user found. Create a superuser first, or pass --user-id/--email.")

        base_url = (opts.get("base_url") or getattr(django_settings, "BASE_URL", "") or "http://localhost:8000").strip()
        if base_url and not base_url.lower().startswith(("http://", "https://")):
            base_url = f"http://{base_url}"
        base_url = base_url.rstrip("/")

        updates = [
            {"key": "portal_enabled", "value": True},
            {"key": "portal_customer_enabled", "value": True},
            {"key": "portal_supplier_enabled", "value": True},
            {"key": "portal_base_url", "value": base_url},
            {"key": "portal_welcome_whatsapp", "value": True},
            {"key": "portal_welcome_sms", "value": True},
            {"key": "portal_welcome_email", "value": True},
        ]

        if not bool(opts.get("force")):
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
        self.stdout.write(self.style.SUCCESS(f"Applied demo portal settings: {len(updated)} updated."))

