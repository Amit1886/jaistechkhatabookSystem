from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from commerce.models import Invoice, Order, Payment
from khataapp.models import Party, ReminderLog
from smart_khata.services.credit_score import sync_invoice_status, update_party_credit_metrics, upsert_payment_behavior_for_invoice


class Command(BaseCommand):
    help = "Seed demo data for Smart Khata (customers, invoices, payments, reminders)."

    def add_arguments(self, parser):
        parser.add_argument("--owner-id", type=int, default=None)

    def handle(self, *args, **options):
        owner_id = options.get("owner_id")
        User = get_user_model()
        owner = None
        if owner_id:
            owner = User.objects.filter(id=int(owner_id)).first()
        if not owner:
            owner = User.objects.filter(is_active=True).order_by("id").first()
        if not owner:
            self.stdout.write(self.style.ERROR("No active user found. Create a user first."))
            return

        today = timezone.now()

        cust1, _ = Party.objects.get_or_create(
            owner=owner,
            party_type="customer",
            name="Demo Customer (On Time)",
            defaults={"mobile": "9999990001", "credit_period": 15, "is_active": True},
        )
        cust2, _ = Party.objects.get_or_create(
            owner=owner,
            party_type="customer",
            name="Demo Customer (Late)",
            defaults={"mobile": "9999990002", "credit_period": 10, "is_active": True},
        )
        cust3, _ = Party.objects.get_or_create(
            owner=owner,
            party_type="customer",
            name="Demo Customer (Overdue)",
            defaults={"mobile": "9999990003", "credit_period": 7, "is_active": True},
        )

        def _make_invoice(party: Party, amount: Decimal, created_at):
            order = Order.objects.create(owner=owner, party=party, order_type="SALE", status="completed", placed_by="user")
            Order.objects.filter(id=order.id).update(created_at=created_at)
            inv = Invoice.objects.create(order=order, amount=amount, gst_type="NON_GST")
            Invoice.objects.filter(id=inv.id).update(created_at=created_at)
            inv.refresh_from_db()
            return inv

        inv1 = _make_invoice(cust1, Decimal("2500.00"), today - timedelta(days=12))
        inv2 = _make_invoice(cust2, Decimal("5000.00"), today - timedelta(days=25))
        inv3 = _make_invoice(cust3, Decimal("1800.00"), today - timedelta(days=20))

        # Payments:
        p1 = Payment.objects.create(invoice=inv1, amount=Decimal("2500.00"), method="cash")
        Payment.objects.filter(id=p1.id).update(created_at=today - timedelta(days=1))
        inv1.refresh_from_db()
        sync_invoice_status(inv1)
        upsert_payment_behavior_for_invoice(inv1)

        p2 = Payment.objects.create(invoice=inv2, amount=Decimal("5000.00"), method="upi")
        Payment.objects.filter(id=p2.id).update(created_at=today - timedelta(days=5))
        inv2.refresh_from_db()
        sync_invoice_status(inv2)
        upsert_payment_behavior_for_invoice(inv2)

        # Reminder log for overdue customer
        ReminderLog.objects.create(
            party=cust3,
            invoice=inv3,
            reminder_type="due",
            tone="strict",
            channel="whatsapp",
            status="sent",
            scheduled_for=today - timedelta(hours=2),
            sent_at=today - timedelta(hours=2),
            payload={"demo": True, "offset": 7, "invoice_number": inv3.number},
        )

        # Refresh metrics
        for c in (cust1, cust2, cust3):
            try:
                update_party_credit_metrics(c)
            except Exception:
                pass

        self.stdout.write(self.style.SUCCESS(f"Seeded Smart Khata demo for owner={owner.id}."))
