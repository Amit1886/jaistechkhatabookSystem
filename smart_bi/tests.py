from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Expense
from commerce.models import Inventory, Invoice, Order, OrderItem, Product
from khataapp.models import Party
from smart_bi.models import DuplicateInvoiceSettings, FestivalCampaign
from smart_bi.services.business_health import compute_business_metric
from smart_bi.services.duplicate_invoices import find_possible_duplicate_invoices
from smart_bi.services.festival import apply_festival_discount


class SmartBITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="bi@example.com",
            password="pass12345",
            username="biuser",
            mobile="9999999999",
        )

    def _product(self, *, name="Item A", price=Decimal("100.00"), sku="SKU-A"):
        return Product.objects.create(
            owner=self.user,
            name=name,
            price=price,
            stock=100,
            min_stock=0,
            sku=sku,
        )

    def _customer(self, *, name="Customer"):
        return Party.objects.create(owner=self.user, name=name, party_type="customer")

    def test_duplicate_invoice_detection_strict(self):
        customer = self._customer()
        product = self._product()

        order1 = Order.objects.create(owner=self.user, party=customer, order_type="SALE", status="pending")
        OrderItem.objects.create(order=order1, product=product, qty=2, price=Decimal("50.00"))
        inv1 = Invoice.objects.create(order=order1)

        order2 = Order.objects.create(owner=self.user, party=customer, order_type="SALE", status="pending")
        OrderItem.objects.create(order=order2, product=product, qty=2, price=Decimal("50.00"))

        settings = DuplicateInvoiceSettings.get_for_owner(self.user)
        settings.enabled = True
        settings.window_minutes = 120
        settings.strict_mode = True
        settings.similarity_threshold = Decimal("90.00")
        settings.save()

        candidates = find_possible_duplicate_invoices(order=order2, settings=settings, max_results=5)
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].invoice.id, inv1.id)
        self.assertEqual(candidates[0].similarity_score, Decimal("100.00"))

    def test_festival_discount_applies_to_order(self):
        today = timezone.localdate()
        customer = self._customer()
        product = self._product(sku="SKU-FEST")

        campaign = FestivalCampaign.objects.create(
            owner=self.user,
            name="Holi Discount",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=3),
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            theme="holi",
            status="active",
        )
        campaign.products.add(product)

        order = Order.objects.create(owner=self.user, party=customer, order_type="SALE", status="pending")
        OrderItem.objects.create(order=order, product=product, qty=1, price=Decimal("100.00"))
        order.save()

        discount = apply_festival_discount(order, day=today, save=True)
        order.refresh_from_db()
        self.assertEqual(discount, Decimal("10.00"))
        self.assertEqual(order.festival_campaign_id, campaign.id)
        self.assertEqual(order.total_amount().quantize(Decimal("0.01")), Decimal("90.00"))

    def test_business_metric_computation(self):
        today = timezone.localdate()
        customer = self._customer()
        supplier = Party.objects.create(owner=self.user, name="Supplier", party_type="supplier")
        product = self._product(sku="SKU-METRIC", price=Decimal("100.00"))

        Inventory.objects.create(owner=self.user, product=product, stock=10)

        sale_order = Order.objects.create(owner=self.user, party=customer, order_type="SALE", status="pending")
        OrderItem.objects.create(order=sale_order, product=product, qty=1, price=Decimal("100.00"))
        Invoice.objects.create(order=sale_order)

        purchase_order = Order.objects.create(owner=self.user, party=supplier, order_type="PURCHASE", status="pending")
        OrderItem.objects.create(order=purchase_order, product=product, qty=1, price=Decimal("40.00"))
        Invoice.objects.create(order=purchase_order)

        Expense.objects.create(
            expense_number="EXP-0001",
            expense_date=today,
            amount_paid=Decimal("10.00"),
            created_by=self.user,
        )

        metric = compute_business_metric(self.user, day=today)
        self.assertEqual(metric.total_sales, Decimal("100.00"))
        self.assertEqual(metric.total_expense, Decimal("10.00"))
        self.assertEqual(metric.total_profit, Decimal("50.00"))
        self.assertGreaterEqual(metric.health_score, 0)
        self.assertLessEqual(metric.health_score, 100)

    def test_festival_campaign_list_renders(self):
        today = timezone.localdate()
        FestivalCampaign.objects.create(
            owner=self.user,
            name="Diwali Sale",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            discount_type="percentage",
            discount_value=Decimal("5.00"),
            theme="diwali",
            status="active",
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("smart_bi:festival_campaign_list"))
        self.assertEqual(response.status_code, 200)
