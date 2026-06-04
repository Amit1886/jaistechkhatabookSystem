from __future__ import annotations

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from smart_bi.services.business_health import upsert_business_metric


class Command(BaseCommand):
    help = "Compute/update BusinessMetric rows for all active users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            dest="date",
            default="",
            help="Anchor date in YYYY-MM-DD (default: today).",
        )
        parser.add_argument(
            "--days",
            dest="days",
            type=int,
            default=1,
            help="How many days to compute backwards from --date (default: 1).",
        )

    def handle(self, *args, **options):
        date_raw = (options.get("date") or "").strip()
        days = int(options.get("days") or 1)
        if days <= 0:
            days = 1

        if date_raw:
            try:
                anchor = datetime.strptime(date_raw, "%Y-%m-%d").date()
            except Exception:
                anchor = timezone.localdate()
        else:
            anchor = timezone.localdate()

        User = get_user_model()
        users = User.objects.filter(is_active=True).only("id")
        total = users.count()

        updated = 0
        for u in users.iterator():
            for i in range(days):
                day = anchor - timedelta(days=i)
                try:
                    upsert_business_metric(u, day=day)
                except Exception:
                    continue
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated business metrics for {updated}/{total} users (days={days}, anchor={anchor})."))

