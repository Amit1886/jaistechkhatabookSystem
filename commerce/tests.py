from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from commerce.models import Order, OrderItem, Product, Warehouse
from khataapp.models import Party


class SalesVoucherCreateViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="user@example.com",
            password="pass12345",
            username="user",
            mobile="9999999999",
        )
        self.client.login(email="user@example.com", password="pass12345")
        # FeatureGateMiddleware blocks /commerce/sales/* behind the `commerce.orders` feature.
        # In production, users typically have an active plan/feature set via signup flows.
        # For unit tests, enable the required feature explicitly.
        try:
            from billing.models import FeatureRegistry, UserFeatureOverride

            feat = FeatureRegistry.objects.filter(key="commerce.orders").first()
            if feat:
                UserFeatureOverride.objects.update_or_create(
                    user=self.user,
                    feature=feat,
                    defaults={"is_enabled": True, "note": "test override"},
                )
        except Exception:
            pass

    def test_get_order_linked_voucher_autofills_remaining_items(self):
        party = Party.objects.create(owner=self.user, name="Test Party", party_type="customer")
        warehouse = Warehouse.objects.create(name="Main")
        product = Product.objects.create(
            owner=self.user,
            name="Item A",
            price=Decimal("100.00"),
            stock=10,
            min_stock=0,
            sku="SKU-ITEM-A",
        )
        order = Order.objects.create(owner=self.user, party=party, warehouse=warehouse)

        # Remaining item (should appear in formset).
        remaining_item = OrderItem.objects.create(
            order=order,
            product=product,
            qty=5,
            price=Decimal("100.00"),
            invoiced_qty=Decimal("2.00"),
            warehouse=warehouse,
        )

        # Fully invoiced item (should be skipped by initial builder).
        OrderItem.objects.create(
            order=order,
            product=product,
            qty=1,
            price=Decimal("50.00"),
            invoiced_qty=Decimal("1.00"),
            warehouse=warehouse,
        )

        response = self.client.get(reverse("commerce:sales_voucher_create"), {"order_id": order.id})
        self.assertEqual(response.status_code, 200)

        formset = response.context["formset"]
        self.assertEqual(formset.total_form_count(), 1)

        form = formset.forms[0]
        self.assertEqual(int(form.initial["source_order_item"]), remaining_item.id)
        self.assertEqual(form.remaining_qty, Decimal("3.00"))
