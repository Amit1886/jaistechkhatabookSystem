from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from decimal import Decimal

from billing.services import ensure_free_plan, get_effective_plan
from core_settings.models import CompanySettings
from accounts.models import UserProfile as AccountsUserProfile
from khataapp.models import Party, UserProfile
from commerce.models import Product


class Command(BaseCommand):
    help = "Create demo users for QA (Demotest3 + Superadmin)"

    def handle(self, *args, **options):
        User = get_user_model()

        company, _ = CompanySettings.objects.get_or_create(company_name="JaisTech Demo Company")

        # Standard ERP role groups (used by role gating)
        role_groups = {}
        for name in ["Super Admin", "Admin", "Agent", "User"]:
            role_groups[name], _ = Group.objects.get_or_create(name=name)

        # Superadmin
        super_username = "Superadmin"
        super_password = "Admin@123"
        super_email = "superadmin@example.com"
        superuser, created = User.objects.get_or_create(
            username=super_username,
            defaults={"email": super_email, "is_staff": True, "is_superuser": True, "is_active": True},
        )
        if created:
            superuser.set_password(super_password)
            superuser.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("OK: Superadmin created"))
        else:
            if not superuser.is_superuser:
                superuser.is_staff = True
                superuser.is_superuser = True
                superuser.is_active = True
                superuser.save(update_fields=["is_staff", "is_superuser", "is_active"])
            self.stdout.write("INFO: Superadmin already exists")

        UserProfile.objects.get_or_create(
            user=superuser,
            defaults={"full_name": "Super Admin", "business_name": "KhataPro HQ", "created_from": "admin"},
        )
        AccountsUserProfile.objects.get_or_create(
            user=superuser,
            defaults={
                "company": company,
                "full_name": "Super Admin",
                "mobile": "9999999999",
                "business_name": "KhataPro HQ",
                "plan": get_effective_plan(superuser),
            },
        )
        superuser.groups.add(role_groups["Super Admin"])

        # Demo user
        demo_username = "Demotest3"
        demo_password = "Demo@123"
        demo_email = "demotest3@example.com"
        demo_user = User.objects.filter(username__iexact=demo_username).order_by("id").first()
        demo_created = demo_user is None
        if demo_user is None:
            demo_user = User.objects.create(
                username=demo_username,
                email=demo_email,
                is_active=True,
            )
        if demo_created:
            demo_user.set_password(demo_password)
            demo_user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("OK: Demotest3 created"))
        else:
            self.stdout.write("INFO: Demotest3 already exists")

        ensure_free_plan(demo_user)
        plan = get_effective_plan(demo_user)
        profile, _ = UserProfile.objects.get_or_create(
            user=demo_user,
            defaults={"full_name": "Demo Test 3", "business_name": "Demo Business", "created_from": "admin"},
        )
        if plan and profile.plan_id != plan.id:
            profile.plan = plan
            profile.save(update_fields=["plan"])

        AccountsUserProfile.objects.get_or_create(
            user=demo_user,
            defaults={
                "company": company,
                "full_name": "Demo Test 3",
                "mobile": "9999999999",
                "business_name": "Demo Business",
                "plan": plan,
            },
        )

        # Billing Model Hierarchy demo values (visible in Profile + Demo Center)
        try:
            from billing.hierarchy import apply_billing_defaults_to_user

            demo_user.billing_access_level = "user"
            demo_user.billing_role_type = "vendor"
            demo_user.billing_child_role = "shop_manager"
            apply_billing_defaults_to_user(demo_user, overwrite=False)
            demo_user.save(
                update_fields=[
                    "billing_access_level",
                    "billing_role_type",
                    "billing_child_role",
                    "permissions_json",
                ]
            )
        except Exception:
            pass
        demo_user.groups.add(role_groups["Admin"])

        # Live mobile app demo data used by Flutter /api/app/* endpoints.
        demo_parties = [
            ("Amit Sharma", "customer", "9000000001", "Delhi", "12000.00"),
            ("Priya Verma", "customer", "9000000002", "Mumbai", "5400.00"),
            ("Rahul Traders", "supplier", "9000000003", "Jaipur", "0.00"),
            ("Neha Patel", "customer", "9000000004", "Bengaluru", "2200.00"),
        ]
        for name, party_type, mobile, address, opening in demo_parties:
            Party.objects.update_or_create(
                owner=demo_user,
                mobile=mobile,
                defaults={
                    "name": name,
                    "party_type": party_type,
                    "address": address,
                    "opening_balance": Decimal(opening),
                },
            )

        demo_products = [
            ("iPhone 15 Pro", "DEMO-IP15PRO", "135000.00", 23, "pcs", "18.00"),
            ("Samsung S24 Ultra", "DEMO-S24U", "79099.00", 18, "pcs", "18.00"),
            ("Boat Headphone", "DEMO-BOAT-HP", "2499.00", 12, "pcs", "18.00"),
            ("Nike Air Max", "DEMO-NIKE-AIR", "4099.00", 8, "pair", "12.00"),
            ("MacBook Air M2", "DEMO-MBA-M2", "114000.00", 5, "pcs", "18.00"),
            ("Coca Cola", "DEMO-COKE", "50.00", 120, "bottle", "5.00"),
        ]
        for name, sku, price, stock, unit, gst_rate in demo_products:
            Product.objects.update_or_create(
                owner=demo_user,
                sku=sku,
                defaults={
                    "name": name,
                    "price": Decimal(price),
                    "stock": stock,
                    "unit": unit,
                    "gst_rate": Decimal(gst_rate),
                    "description": "Demo Business live mobile app product",
                },
            )
        self.stdout.write(self.style.SUCCESS("OK: Seeded mobile app customers + products"))

        # Linked users under Demotest3 (Billing Dashboard -> Manage Users)
        try:
            from billing.hierarchy import apply_billing_defaults_to_user

            def _upsert_linked(username: str, email: str, mobile: str, role_type: str, child_role: str):
                u, created = User.objects.get_or_create(
                    email=email,
                    defaults={"username": username, "mobile": mobile, "is_active": True},
                )
                if created:
                    u.set_password(demo_password)
                u.parent = demo_user
                u.billing_access_level = ""
                u.billing_role_type = role_type
                u.billing_child_role = child_role
                apply_billing_defaults_to_user(u, overwrite=False)
                u.save()
                try:
                    ensure_free_plan(u)
                except Exception:
                    pass
                return u

            _upsert_linked("DemoSubUser1", "demotest3.sub1@example.com", "9000000101", "sub_user", "data_entry")
            _upsert_linked("DemoCustomer1", "demotest3.customer1@example.com", "9000000102", "customer", "authorized_user")
            _upsert_linked("DemoSupplier1", "demotest3.supplier1@example.com", "9000000103", "supplier", "purchase_manager")
            _upsert_linked("DemoFieldAgent1", "demotest3.agent1@example.com", "9000000104", "field_agent", "field_executive")
        except Exception:
            pass

        # ---------------- Storefront Customer Demo ----------------
        # Same auth system (accounts:login). This user has no vendor access by default.
        customer_username = "CustomerDemo"
        customer_password = "Customer@123"
        customer_email = "customer.demo@example.com"
        customer_user, customer_created = User.objects.get_or_create(
            username=customer_username,
            defaults={"email": customer_email, "is_active": True},
        )
        if customer_created:
            customer_user.set_password(customer_password)
            customer_user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS("OK: CustomerDemo created"))
        else:
            self.stdout.write("INFO: CustomerDemo already exists")
        # Intentionally do NOT add ERP groups by default.
        # Admin can grant ERP/Billing access later by assigning the relevant group.

        # ---------------- Marketplace Demo (Vendor + Shiprocket) ----------------
        try:
            from vendors.models import Vendor, VendorShippingProviderConfig, VendorWarehouse
            from warehouse.models import Warehouse
            from storefront.models import PlatformSettings
        except Exception:
            Vendor = None
            Warehouse = None

        if Vendor and Warehouse:
            demo_warehouse, _ = Warehouse.objects.get_or_create(
                code="DEMO",
                defaults={"name": "Demo Warehouse", "address": "Demo Address", "is_dark_store": True, "is_active": True},
            )

            demo_vendor, vendor_created = Vendor.objects.get_or_create(
                owner=demo_user,
                defaults={"name": "Demo Store", "subdomain": "demo", "primary_warehouse": demo_warehouse, "is_active": True},
            )
            if not vendor_created and not demo_vendor.primary_warehouse_id:
                demo_vendor.primary_warehouse = demo_warehouse
                demo_vendor.save(update_fields=["primary_warehouse", "updated_at"])

            VendorWarehouse.objects.get_or_create(vendor=demo_vendor, warehouse=demo_warehouse, defaults={"is_active": True})

            # Shiprocket credentials should be supplied via environment variables (recommended).
            import os

            shiprocket_email = (os.getenv("SHIPROCKET_EMAIL") or os.getenv("SHIPROCKET_DEMO_EMAIL") or "demo@example.com").strip()
            shiprocket_password = (os.getenv("SHIPROCKET_PASSWORD") or os.getenv("SHIPROCKET_DEMO_PASSWORD") or "DEMO_PASSWORD_CHANGE_ME").strip()
            webhook_secret = (os.getenv("SHIPROCKET_WEBHOOK_SECRET") or "DEMO_SHIPROCKET_WEBHOOK_SECRET").strip()

            shiprocket_cfg, _ = VendorShippingProviderConfig.objects.update_or_create(
                vendor=demo_vendor,
                provider=VendorShippingProviderConfig.Provider.SHIPROCKET,
                defaults={
                    "is_active": True,
                    "config": {
                        "api_base": "https://apiv2.shiprocket.in",
                        "mode": "demo" if shiprocket_password == "DEMO_PASSWORD_CHANGE_ME" else "live",
                        "email": shiprocket_email,
                        "password": shiprocket_password,
                        "pickup_location": "Primary",
                        "webhook_secret": webhook_secret,
                    },
                },
            )

            self.stdout.write(self.style.SUCCESS("OK: Demo vendor + Shiprocket config ready"))
            self.stdout.write("Marketplace Demo:")
            self.stdout.write(f"  - Vendor subdomain: {demo_vendor.subdomain}")
            self.stdout.write(f"  - Shiprocket config active: {shiprocket_cfg.is_active}")
            if shiprocket_password == "DEMO_PASSWORD_CHANGE_ME":
                self.stdout.write(
                    self.style.WARNING("  - Shiprocket password is a placeholder. Set SHIPROCKET_PASSWORD in .env for real testing.")
                )

            # Platform settings (commission wallet owner defaults to superadmin)
            try:
                PlatformSettings.objects.get_or_create(
                    id=1,
                    defaults={"platform_user": superuser, "commission_percent": 2},
                )
            except Exception:
                pass

            # Payment gateway demo (vendor-specific; configured by admin)
            try:
                from vendors.models import VendorPaymentGatewayConfig

                VendorPaymentGatewayConfig.objects.update_or_create(
                    vendor=demo_vendor,
                    provider=VendorPaymentGatewayConfig.Provider.RAZORPAY,
                    defaults={
                        "is_active": True,
                        "config": {
                            "mode": "demo",
                            "key_id": "rzp_test_DEMO_KEY",
                            "key_secret": "DEMO_SECRET",
                        },
                    },
                )
                self.stdout.write(self.style.SUCCESS("OK: Seeded demo payment gateway (Razorpay demo mode)"))
            except Exception:
                pass

            # Coupons / offers demo (created in billing/commerce, enabled for vendor store)
            try:
                from commerce.models import Coupon
                from django.utils import timezone
                from storefront.models import VendorCoupon

                now = timezone.now()
                c1, _ = Coupon.objects.get_or_create(
                    code="DEMO50",
                    defaults={
                        "title": "Demo 50% OFF",
                        "description": "50% off up to ₹100 (demo)",
                        "coupon_type": "discount",
                        "discount_type": "percentage",
                        "discount_value": Decimal("50.00"),
                        "max_discount": Decimal("100.00"),
                        "usage_limit": 5000,
                        "per_user_limit": 20,
                        "min_order_amount": Decimal("199.00"),
                        "valid_from": now,
                        "valid_until": None,
                        "is_active": True,
                    },
                )
                c2, _ = Coupon.objects.get_or_create(
                    code="WELCOME25",
                    defaults={
                        "title": "Welcome ₹25 OFF",
                        "description": "Flat ₹25 off for new users (demo)",
                        "coupon_type": "discount",
                        "discount_type": "fixed",
                        "discount_value": Decimal("25.00"),
                        "max_discount": None,
                        "usage_limit": 10000,
                        "per_user_limit": 5,
                        "min_order_amount": Decimal("99.00"),
                        "valid_from": now,
                        "valid_until": None,
                        "is_active": True,
                    },
                )
                VendorCoupon.objects.update_or_create(vendor=demo_vendor, coupon=c1, defaults={"is_active": True})
                VendorCoupon.objects.update_or_create(vendor=demo_vendor, coupon=c2, defaults={"is_active": True})
                self.stdout.write(self.style.SUCCESS("OK: Seeded demo coupons for storefront (DEMO50, WELCOME25)"))
            except Exception:
                pass

        self.stdout.write("Credentials:")
        self.stdout.write(f"  - Superadmin / {super_password}")
        self.stdout.write(f"  - Demotest3 / {demo_password}")
        self.stdout.write("  - CustomerDemo / Customer@123 (no Billing/Vendor access by default)")
