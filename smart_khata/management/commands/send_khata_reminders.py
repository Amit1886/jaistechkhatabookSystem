from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from smart_khata.services.reminders import send_due_reminders_for_owner


class Command(BaseCommand):
    help = "Send Smart Khata due reminders (WhatsApp/SMS/Email) based on configured schedule offsets."

    def add_arguments(self, parser):
        parser.add_argument("--owner-id", type=int, default=None, help="Run for a single business owner (user id).")
        parser.add_argument("--dry-run", action="store_true", help="Do not send; only create scheduled logs.")
        parser.add_argument("--limit", type=int, default=200, help="Max invoices processed per owner.")

    def handle(self, *args, **options):
        owner_id = options.get("owner_id")
        dry_run = bool(options.get("dry_run"))
        limit = int(options.get("limit") or 200)

        User = get_user_model()
        owners_qs = User.objects.filter(is_active=True)
        if owner_id:
            owners_qs = owners_qs.filter(id=int(owner_id))

        totals = {"owners": 0, "sent": 0, "skipped": 0, "errors": 0}

        for owner in owners_qs.iterator(chunk_size=200):
            totals["owners"] += 1
            res = send_due_reminders_for_owner(owner, dry_run=dry_run, limit=limit)
            totals["sent"] += int(res.get("sent") or 0)
            totals["skipped"] += int(res.get("skipped") or 0)
            totals["errors"] += int(res.get("errors") or 0)
            self.stdout.write(
                f"owner={owner.id} status={res.get('status')} sent={res.get('sent')} skipped={res.get('skipped')} errors={res.get('errors')}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. owners={totals['owners']} sent={totals['sent']} skipped={totals['skipped']} errors={totals['errors']}"
            )
        )

