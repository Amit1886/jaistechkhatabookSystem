from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from retail_os.models import Branch, IoTDevice, MediaAsset, OfferCampaign, PricingRule, RetailScreen


class Command(BaseCommand):
    help = "Seed a small Retail OS demo control layer without changing existing UI."

    def handle(self, *args, **options):
        branch, _ = Branch.objects.get_or_create(
            code="MAIN",
            defaults={"name": "Main Retail Branch", "branch_type": Branch.BranchType.STORE, "city": "Local"},
        )
        PricingRule.objects.get_or_create(
            name="Low stock smart price lift",
            condition_type=PricingRule.ConditionType.STOCK_LOW,
            defaults={
                "adjustment_type": PricingRule.AdjustmentType.PERCENT,
                "adjustment_value": "5.00",
                "stock_threshold": 3,
                "branch": branch,
                "offer_tag": "Limited stock",
            },
        )
        now = timezone.now()
        OfferCampaign.objects.get_or_create(
            name="Happy Hour Flash Deal",
            defaults={
                "status": OfferCampaign.Status.SCHEDULED,
                "starts_at": now,
                "ends_at": now + timedelta(hours=2),
                "discount_percent": "10.00",
                "badge_text": "Happy Hour",
            },
        )
        screen, _ = RetailScreen.objects.get_or_create(device_uid="TV-MAIN-001", defaults={"name": "Main Entrance TV", "branch": branch})
        MediaAsset.objects.get_or_create(title="Welcome Offer Slide", defaults={"media_type": MediaAsset.MediaType.HTML, "html_content": "<h1>Today Offers</h1>"})
        IoTDevice.objects.get_or_create(
            device_uid="SCALE-MAIN-001",
            defaults={"name": "Counter Weighing Scale", "device_type": IoTDevice.DeviceType.SCALE, "branch": branch},
        )
        self.stdout.write(self.style.SUCCESS(f"Retail OS demo seeded for {branch.code} with screen {screen.device_uid}"))
