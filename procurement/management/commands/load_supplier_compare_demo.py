from __future__ import annotations

from decimal import Decimal
import random

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from commerce.models import Category, Product
from khataapp.models import Party
from procurement.models import SupplierProduct, SupplierRating


class Command(BaseCommand):
    help = "Create demo suppliers + supplier-product mappings for Supplier Price Comparison module."

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, help="Owner user email to attach demo data to")
        parser.add_argument("--user-id", type=int, help="Owner user ID to attach demo data to")

    def handle(self, *args, **options):
        email = (options.get("email") or "").strip()
        user_id = options.get("user_id")

        user = None
        if user_id:
            user = User.objects.filter(id=user_id).first()
        if not user and email:
            user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError("Provide --email or --user-id for an existing user.")

        cat, _ = Category.objects.get_or_create(owner=user, name="General", defaults={"description": "Demo category"})

        products = list(Product.objects.filter(owner=user).order_by("id")[:3])
        if not products:
            for i in range(1, 4):
                sku = f"DEMO-SKU-{user.id}-{i}"
                prod, _ = Product.objects.get_or_create(
                    owner=user,
                    sku=sku,
                    defaults={
                        "name": f"Demo Product {i}",
                        "category": cat,
                        "price": Decimal("120.00") + (i * Decimal("10.00")),
                        "stock": random.randint(0, 5),
                        "min_stock": 5,
                        "unit": "pcs",
                        "created_at": timezone.now(),
                    },
                )
                products.append(prod)

        supplier_a, _ = Party.objects.get_or_create(
            owner=user,
            party_type="supplier",
            name="Demo Supplier A",
            defaults={"mobile": "9999999991", "whatsapp_number": "9999999991", "is_active": True},
        )
        supplier_b, _ = Party.objects.get_or_create(
            owner=user,
            party_type="supplier",
            name="Demo Supplier B",
            defaults={"mobile": "9999999992", "whatsapp_number": "9999999992", "is_active": True},
        )
        supplier_c, _ = Party.objects.get_or_create(
            owner=user,
            party_type="supplier",
            name="Demo Supplier C",
            defaults={"mobile": "9999999993", "whatsapp_number": "9999999993", "is_active": True},
        )

        suppliers = [supplier_a, supplier_b, supplier_c]
        created_map = 0
        for p in products:
            base = Decimal("100.00") + Decimal(str(random.randint(0, 25)))
            for idx, s in enumerate(suppliers):
                sp, created = SupplierProduct.objects.get_or_create(owner=user, supplier=s, product=p)
                if created:
                    created_map += 1
                sp.price = (base + Decimal(str(idx * 7))).quantize(Decimal("0.01"))
                sp.moq = 1 + idx
                sp.delivery_days = 2 + idx
                sp.is_active = True
                sp._updated_by = user
                sp.save()

        SupplierRating.objects.update_or_create(
            owner=user,
            supplier=supplier_a,
            rated_by=user,
            defaults={"delivery_speed": 4, "product_quality": 4, "pricing": 3, "comment": "Good overall"},
        )
        SupplierRating.objects.update_or_create(
            owner=user,
            supplier=supplier_b,
            rated_by=user,
            defaults={"delivery_speed": 5, "product_quality": 3, "pricing": 4, "comment": "Fast delivery"},
        )
        SupplierRating.objects.update_or_create(
            owner=user,
            supplier=supplier_c,
            rated_by=user,
            defaults={"delivery_speed": 3, "product_quality": 5, "pricing": 2, "comment": "Best quality"},
        )

        self.stdout.write(self.style.SUCCESS(f"Demo data ready for {user.email}."))
        self.stdout.write(self.style.SUCCESS(f"Suppliers: {len(suppliers)} | Products: {len(products)} | Mappings created: {created_map}"))

