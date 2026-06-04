from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from products.models import Category, Product, WarehouseInventory
from vendors.models import Vendor, VendorWarehouse
from warehouse.models import Warehouse


class Command(BaseCommand):
    help = "Seed demo marketplace data (products + inventory + online listings)"

    @transaction.atomic
    def handle(self, *args, **options):
        demo_vendor = Vendor.objects.filter(subdomain="demo").first()
        if not demo_vendor:
            self.stderr.write("ERROR: Demo vendor not found. Run `python manage.py seed_demo_users` first.")
            return

        demo_wh = demo_vendor.primary_warehouse or Warehouse.objects.filter(code="DEMO").first()
        if not demo_wh:
            demo_wh = Warehouse.objects.create(code="DEMO", name="Demo Warehouse", address="Demo Address", is_active=True)
            demo_vendor.primary_warehouse = demo_wh
            demo_vendor.save(update_fields=["primary_warehouse", "updated_at"])

        VendorWarehouse.objects.get_or_create(vendor=demo_vendor, warehouse=demo_wh, defaults={"is_active": True})

        cat_fashion, _ = Category.objects.get_or_create(slug="fashion", defaults={"name": "Fashion", "is_active": True})
        cat_kitchen, _ = Category.objects.get_or_create(slug="kitchen", defaults={"name": "Kitchen", "is_active": True})
        cat_mobile, _ = Category.objects.get_or_create(slug="mobile-accessories", defaults={"name": "Mobile Accessories", "is_active": True})

        demo_products = [
            ("Women Kurti", cat_fashion, Decimal("699.00")),
            ("Men T-Shirt", cat_fashion, Decimal("399.00")),
            ("Steel Bottle 1L", cat_kitchen, Decimal("249.00")),
            ("Non-stick Pan", cat_kitchen, Decimal("899.00")),
            ("Phone Cover", cat_mobile, Decimal("199.00")),
            ("Fast Charger 20W", cat_mobile, Decimal("599.00")),
            ("Bluetooth Earbuds", cat_mobile, Decimal("1299.00")),
            ("Saree Premium", cat_fashion, Decimal("1199.00")),
            ("Kids Dress", cat_fashion, Decimal("499.00")),
            ("Lunch Box", cat_kitchen, Decimal("349.00")),
            ("USB Cable", cat_mobile, Decimal("149.00")),
            ("Kitchen Knife Set", cat_kitchen, Decimal("699.00")),
        ]

        created = 0
        for idx, (name, cat, price) in enumerate(demo_products, start=1):
            sku = f"DEMO-SKU-{idx:03d}"
            barcode = f"9900{idx:08d}"
            defaults = {
                "name": name,
                "category": cat,
                "barcode": barcode,
                "gst_percent": Decimal("0.00"),
                "mrp": price,
                "b2b_price": price,
                "b2c_price": price,
                "wholesale_price": price,
                "description": f"Demo product: {name}",
                "is_online": True,
                "slug": slugify(f"{name}-{sku}")[:255],
                "is_active": True,
            }
            p, was_created = Product.objects.update_or_create(sku=sku, defaults=defaults)
            if was_created:
                created += 1
            WarehouseInventory.objects.update_or_create(
                warehouse=demo_wh, product=p, defaults={"available_qty": 50, "reserved_qty": 0}
            )

        self.stdout.write(self.style.SUCCESS(f"OK: Seeded marketplace demo products. Created={created}"))
        self.stdout.write("Storefront URL:")
        self.stdout.write("  - http://127.0.0.1:8080/store/demo/")

