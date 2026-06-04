from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from commerce.models import Invoice, Order, OrderItem, Payment, Product
from khataapp.core_engine.models.engine import BusinessGrowthEngine
from khataapp.core_engine.models.loyalty import LoyaltyAccount
from khataapp.core_engine.models.logs import RewardLedgerEntry
from khataapp.models import Party, UserProfile


class CentralEngineTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="engine@example.com",
            password="pass12345",
            username="engineuser",
            mobile="9000000000",
            is_staff=True,  # bypass plan feature gates in tests
        )
        UserProfile.objects.get_or_create(user=self.user, defaults={"full_name": "Engine User", "business_name": "Engine Biz"})

    def test_engine_dashboard_creates_engine(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("central_engine:dashboard"))
        self.assertEqual(resp.status_code, 200)
        eng = BusinessGrowthEngine.objects.filter(owner=self.user).first()
        self.assertIsNotNone(eng)
        self.assertTrue(bool(eng.referral_code))

    def test_party_transaction_awards_loyalty_and_tasks(self):
        party = Party.objects.create(owner=self.user, name="Customer", party_type="customer")
        # Party signal creates loyalty account
        self.assertTrue(LoyaltyAccount.objects.filter(party=party).exists())

        # Transaction -> loyalty points
        from khataapp.models import Transaction

        Transaction.objects.create(
            party=party,
            txn_type="credit",
            txn_mode="cash",
            amount=Decimal("500.00"),
            date=timezone.localdate(),
        )
        acct = LoyaltyAccount.objects.get(party=party)
        self.assertGreaterEqual(acct.points, 5)
        self.assertTrue(RewardLedgerEntry.objects.filter(owner=self.user).exists())

    def test_invoice_and_payment_update_rewards_and_commission(self):
        party = Party.objects.create(owner=self.user, name="Customer2", party_type="customer")
        product = Product.objects.create(owner=self.user, name="Item", price=Decimal("100.00"), stock=10, min_stock=0, sku="SKU-CE-1")
        order = Order.objects.create(owner=self.user, party=party, order_type="SALE", status="pending")
        OrderItem.objects.create(order=order, product=product, qty=1, price=Decimal("100.00"))
        inv = Invoice.objects.create(order=order, gst_type="GST")
        Payment.objects.create(invoice=inv, amount=inv.amount, method="upi")

        eng = BusinessGrowthEngine.objects.get(owner=self.user)
        self.assertGreaterEqual(eng.total_rewards, 0)
        self.assertGreaterEqual(eng.reward_points, 0)
        self.assertGreater(eng.payment_commission_earned, Decimal("0.00"))

