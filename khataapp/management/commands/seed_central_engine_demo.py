from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from billing.models import FeatureRegistry, Plan, PlanFeature
from billing.services import sync_feature_registry
from commerce.models import Invoice, Order, OrderItem, Payment, Product
from khataapp.core_engine.models.engine import BusinessGrowthEngine
from khataapp.core_engine.services.analytics_service import update_engine_snapshot
from khataapp.core_engine.services.daily_tasks import complete_task, ensure_default_tasks
from khataapp.core_engine.services.referral_service import pay_referral_commission, record_referral
from khataapp.core_engine.services.whatsapp_service import queue_message
from khataapp.models import Party, UserProfile


ENGINE_FEATURE_KEYS = [
    "engine.rewards",
    "engine.referrals",
    "engine.payment_links",
    "engine.notifications",
    "engine.loyalty",
    "engine.daily_tasks",
    "engine.analytics",
]


class Command(BaseCommand):
    help = "Seed demo data for the Central Business Engine (Demo user: Demotest3)."

    def handle(self, *args, **options):
        User = get_user_model()

        # Ensure plan feature registry includes engine.* keys.
        sync_feature_registry()

        # Create a paid plan that unlocks engine features.
        plan, _ = Plan.objects.get_or_create(
            name="Growth Pro",
            defaults={
                "price": Decimal("999.00"),
                "price_monthly": Decimal("999.00"),
                "price_yearly": Decimal("9999.00"),
                "trial_days": 7,
                "active": True,
            },
        )
        # Ensure PlanFeature rows exist for this plan (sync_feature_registry only backfills existing plans).
        for key in ENGINE_FEATURE_KEYS:
            feat = FeatureRegistry.objects.filter(key=key, active=True).first()
            if not feat:
                continue
            PlanFeature.objects.get_or_create(plan=plan, feature=feat, defaults={"enabled": True})
            PlanFeature.objects.filter(plan=plan, feature=feat).update(enabled=True)

        # Demo user
        demo_user, created = User.objects.get_or_create(
            username="Demotest3",
            defaults={"email": "demotest3@example.com", "is_active": True},
        )
        if created:
            demo_user.set_password("Demo@123")
            demo_user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("OK: Demotest3 created (password: Demo@123)"))
        else:
            self.stdout.write("INFO: Demotest3 already exists")

        profile, _ = UserProfile.objects.get_or_create(
            user=demo_user,
            defaults={"full_name": "Demo Test 3", "business_name": "Demo Business", "created_from": "admin"},
        )
        if profile.plan_id != plan.id:
            profile.plan = plan
            profile.save(update_fields=["plan"])

        # Ensure engine row exists and credits are preloaded.
        engine, _ = BusinessGrowthEngine.objects.get_or_create(owner=demo_user)
        engine.whatsapp_credits = max(20, int(engine.whatsapp_credits or 0))
        engine.storage_used = int(engine.storage_used or 0) + 1024 * 1024 * 12  # +12MB demo usage
        engine.save(update_fields=["whatsapp_credits", "storage_used", "updated_at"])

        # Parties
        customer1, _ = Party.objects.get_or_create(owner=demo_user, party_type="customer", name="Demo Customer A", defaults={"mobile": "9000000001"})
        customer2, _ = Party.objects.get_or_create(owner=demo_user, party_type="customer", name="Demo Customer B", defaults={"mobile": "9000000002"})

        # Product + Invoice + Payment (triggers invoice/payment signals -> rewards/commission)
        product, _ = Product.objects.get_or_create(
            sku="DEMO-SKU-001",
            defaults={"owner": demo_user, "name": "Demo Item", "price": Decimal("100.00"), "stock": 100, "min_stock": 0},
        )

        order = Order.objects.create(owner=demo_user, party=customer1, order_type="SALE", status="pending")
        OrderItem.objects.create(order=order, product=product, qty=2, price=Decimal("100.00"))
        invoice = Invoice.objects.create(order=order, gst_type="GST")
        Payment.objects.create(invoice=invoice, amount=invoice.amount, method="upi", reference="DEMO-UPI-REF")

        # Daily tasks + streak simulation (3 days)
        ensure_default_tasks()
        today = timezone.localdate()
        for i in range(2, -1, -1):
            d = today - timedelta(days=i)
            complete_task(owner=demo_user, task_key="daily_login", day=d, actor=demo_user)

        # Referral simulation: Demo user refers a new user and earns commission.
        child, _ = User.objects.get_or_create(
            username="DemoChild1",
            defaults={"email": "demochild1@example.com", "is_active": True},
        )
        UserProfile.objects.get_or_create(
            user=child,
            defaults={"full_name": "Demo Child 1", "business_name": "Child Biz", "created_from": "admin", "plan": plan},
        )
        referral = record_referral(referrer=demo_user, referred=child, actor=demo_user, meta={"seed": True})
        if referral:
            pay_referral_commission(referral=referral, gross_commission_amount=Decimal("200.00"), actor=demo_user)

        # Notification demo (queues an OfflineMessage)
        queue_message(
            owner=demo_user,
            channel="whatsapp",
            party=customer2,
            recipient_mobile=customer2.whatsapp_number or customer2.mobile or "",
            message="Demo reminder: Your payment is due. Please pay using the link provided.",
            actor=demo_user,
            meta={"seed": True},
        )

        # Refresh snapshot for dashboards.
        update_engine_snapshot(demo_user)

        self.stdout.write(self.style.SUCCESS("OK: Central Engine demo seed complete."))
        self.stdout.write("Visit: /app/engine/ (Growth Dashboard)")
