from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from commerce.models import Product
from smart_bi.models import DuplicateInvoiceSettings, FestivalCampaign
from smart_bi.services.business_health import upsert_business_metric


class Command(BaseCommand):
    help = "Seed demo data for Smart BI (festival campaign + settings + recent metrics)."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="", help="Seed for a specific user email.")
        parser.add_argument("--username", default="", help="Seed for a specific username.")

    def handle(self, *args, **options):
        email = (options.get("email") or "").strip()
        username = (options.get("username") or "").strip()

        User = get_user_model()
        qs = User.objects.filter(is_active=True)
        if email:
            qs = qs.filter(email=email)
        if username:
            qs = qs.filter(username=username)
        user = qs.first()
        if not user:
            self.stdout.write(self.style.ERROR("No matching user found to seed demo data."))
            return

        settings_obj = DuplicateInvoiceSettings.get_for_owner(user)
        settings_obj.enabled = True
        settings_obj.window_minutes = 90
        settings_obj.strict_mode = False
        settings_obj.similarity_threshold = Decimal("90.00")
        settings_obj.save()

        today = timezone.localdate()

        # Create a "current" campaign for demo purposes.
        camp, _ = FestivalCampaign.objects.update_or_create(
            owner=user,
            name="Holi Discount",
            defaults={
                "start_date": today,
                "end_date": today + timedelta(days=7),
                "discount_type": FestivalCampaign.DiscountType.PERCENTAGE,
                "discount_value": Decimal("12.00"),
                "theme": "holi",
                "status": FestivalCampaign.Status.ACTIVE,
            },
        )
        FestivalCampaign.objects.filter(owner=user).exclude(id=camp.id).update(status=FestivalCampaign.Status.INACTIVE)

        prods = list(Product.objects.filter(owner=user).order_by("id")[:5])
        if prods:
            camp.products.set(prods)

        # Ensure last 7 days metrics exist.
        for i in range(0, 7):
            upsert_business_metric(user, day=today - timedelta(days=i))

        self.stdout.write(self.style.SUCCESS(f"Seeded Smart BI demo data for user={user.id} ({user.email})."))

