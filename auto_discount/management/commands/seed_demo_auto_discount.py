from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seeds demo Auto-Discount settings + sample products/customers."

    def handle(self, *args, **options):
        from auto_discount.models import AppSettings, Customer, Product

        settings = AppSettings.get_solo()
        settings.enable_auto_discount = True
        settings.min_profit_percentage = 10
        settings.b2b_slabs = [
            {"min_qty": 5, "discount": 2},
            {"min_qty": 20, "discount": 5},
            {"min_qty": 50, "discount": 8},
            {"min_qty": 100, "discount": 12},
        ]
        settings.b2c_slabs = [
            {"min_qty": 3, "discount": 1},
            {"min_qty": 10, "discount": 3},
            {"min_qty": 25, "discount": 6},
            {"min_qty": 60, "discount": 10},
        ]
        settings.full_clean()
        settings.save()

        Customer.objects.get_or_create(name="Demo B2B Customer", customer_type=Customer.CustomerType.B2B, defaults={"is_active": True})
        Customer.objects.get_or_create(name="Demo B2C Customer", customer_type=Customer.CustomerType.B2C, defaults={"is_active": True})

        Product.objects.get_or_create(
            name="Demo Rice 10kg",
            defaults={
                "purchase_price": Decimal("520.00"),
                "selling_price": Decimal("650.00"),
                "stock": 120,
                "is_active": True,
            },
        )
        Product.objects.get_or_create(
            name="Demo Oil 1L",
            defaults={
                "purchase_price": Decimal("95.00"),
                "selling_price": Decimal("120.00"),
                "stock": 500,
                "is_active": True,
            },
        )
        Product.objects.get_or_create(
            name="Demo Soap Pack",
            defaults={
                "purchase_price": Decimal("180.00"),
                "selling_price": Decimal("210.00"),
                "stock": 300,
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo auto-discount settings + data created."))
        self.stdout.write("User-side settings: /auto-discount/settings/")
        self.stdout.write("Billing demo: /auto-discount/billing/")

