from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone

from commerce.models import (
    Category,
    Inventory,
    Invoice,
    Order,
    OrderItem,
    Payment,
    Product,
    Warehouse as CommerceWarehouse,
)
from commerce.models import _payment_event
from crm.models import LocalShop
from enterprise_control.models import (
    AuditLog,
    DashboardWidget,
    DynamicModule,
    PermissionTemplate,
    ThemeConfig,
    UserWorkspace,
    Workspace,
)
from khataapp.models import FieldAgent, Party, Transaction
from khataapp.models import update_party_grade_and_notify
from saas.models import PermissionNode, RoleTemplate, RoleTemplatePermission, UserPermissionGraph, UserPermissionOverride
from vendors.models import Vendor, VendorMembership, VendorStoreSettings, VendorWarehouse


PASSWORD = "Demo@12345"


DEMO_USERS = {
    "Demotest3": {
        "email": "demotest3@example.com",
        "mobile": "9000000300",
        "role": "admin",
        "full_name": "Demo Enterprise Admin",
        "workspace": "admin_workspace",
        "staff": True,
    },
    "Demotest3POS": {
        "email": "demotest3.pos@example.com",
        "mobile": "9000000301",
        "role": "pos_user",
        "full_name": "Demo POS Cashier",
        "workspace": "pos_workspace",
    },
    "Demotest3Supplier": {
        "email": "demotest3.supplier@example.com",
        "mobile": "9000000302",
        "role": "supplier",
        "full_name": "Demo Supplier Partner",
        "workspace": "supplier_workspace",
    },
    "Demotest3Vendor": {
        "email": "demotest3.vendor@example.com",
        "mobile": "9000000303",
        "role": "ecommerce_vendor",
        "full_name": "Demo Ecommerce Vendor",
        "workspace": "vendor_workspace",
    },
    "Demotest3CRM": {
        "email": "demotest3.crm@example.com",
        "mobile": "9000000304",
        "role": "crm_user",
        "full_name": "Demo CRM Manager",
        "workspace": "crm_workspace",
    },
    "Demotest3Customer": {
        "email": "demotest3.customer@example.com",
        "mobile": "9000000305",
        "role": "customer",
        "full_name": "Demo Retail Customer",
        "workspace": "customer_workspace",
    },
    "Demotest3Accountant": {
        "email": "demotest3.accounts@example.com",
        "mobile": "9000000306",
        "role": "accountant",
        "full_name": "Demo Accountant",
        "workspace": "admin_workspace",
    },
    "Demotest3Kiosk": {
        "email": "demotest3.kiosk@example.com",
        "mobile": "9000000307",
        "role": "kiosk_user",
        "full_name": "Demo Kiosk Session",
        "workspace": "kiosk_workspace",
    },
}


PRODUCTS = [
    ("BILL-POS-01", "Aurora Barcode Scanner", "POS Hardware", "3499.00", 48, 18),
    ("BILL-POS-02", "Thermal Printer Pro 80mm", "POS Hardware", "6999.00", 32, 18),
    ("BILL-SAA-01", "Retail Cloud Subscription", "SaaS Plans", "9999.00", 500, 18),
    ("BILL-INV-01", "Smart Shelf Sensor", "IoT Inventory", "1499.00", 120, 12),
    ("BILL-ECM-01", "Marketplace Starter Kit", "Ecommerce", "24999.00", 18, 18),
    ("BILL-CRM-01", "AI Follow-up Pack", "CRM", "3999.00", 75, 18),
]


CUSTOMERS = [
    ("Urban Mart And Grocers", "9811100001", "customer", "A", 88),
    ("Northline Pharmacy", "9811100002", "customer", "B", 74),
    ("FreshCart Local", "9811100003", "customer", "A", 91),
    ("Metro Food Court", "9811100004", "customer", "C", 62),
]


SUPPLIERS = [
    ("Prime Device Distributors", "9822200001", "supplier", "A", 83),
    ("NexGen Packaging Supply", "9822200002", "supplier", "B", 71),
    ("Cloud Retail Hardware", "9822200003", "supplier", "A", 89),
]


class Command(BaseCommand):
    help = "Seed the complete Demotest3 enterprise SaaS, POS, ecommerce, CRM, supplier, and Flutter demo ecosystem."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_enterprise_control", verbosity=0)

        users = self._seed_users()
        self._grant_demo_permissions(users)
        self._seed_enterprise_ui(users)
        warehouse = self._seed_warehouse()
        vendor = self._seed_vendor(users["Demotest3Vendor"], warehouse)
        products = self._seed_products(users["Demotest3"], warehouse)
        parties = self._seed_parties(users["Demotest3"])
        self._seed_orders_invoices_payments_offline_safe(users["Demotest3"], parties, products, warehouse)
        self._seed_crm(users)
        self._seed_agent(users, parties)
        self._seed_audit_timeline(users["Demotest3"])

        self.stdout.write(
            self.style.SUCCESS(
                "Demotest3 enterprise demo ecosystem ready. "
                f"Login: Demotest3 / {PASSWORD}. "
                f"Extra users: {', '.join(k for k in DEMO_USERS if k != 'Demotest3')}. "
                f"Vendor: {vendor.subdomain}"
            )
        )

    def _seed_users(self):
        User = get_user_model()
        users = {}
        for username, spec in DEMO_USERS.items():
            user = User.objects.filter(email__iexact=spec["email"]).first()
            if not user:
                user = User.objects.create_user(
                    username=username,
                    email=spec["email"],
                    mobile=spec["mobile"],
                    password=PASSWORD,
                )
            user.username = username
            user.first_name = spec["full_name"].split(" ", 1)[0]
            user.last_name = spec["full_name"].split(" ", 1)[1] if " " in spec["full_name"] else ""
            user.mobile = spec["mobile"]
            user.is_active = True
            user.is_staff = bool(spec.get("staff", False))
            user.primary_role = spec["role"]
            user.permissions_json = {
                "web_access": True,
                "app_access": True,
                "api_access": True,
                "dashboard_view": True,
            }
            user.save()
            users[username] = user
        return users

    def _grant_demo_permissions(self, users):
        all_permission_keys = set(PermissionNode.objects.filter(is_active=True).values_list("key", flat=True))
        admin_role = RoleTemplate.objects.filter(key="admin").first()
        for username, user in users.items():
            role_key = DEMO_USERS[username]["role"]
            role = RoleTemplate.objects.filter(key=role_key).first() or admin_role
            UserPermissionGraph.objects.update_or_create(
                user=user,
                seller=getattr(user, "seller", None),
                defaults={"role": role, "inherit_from_owner": True, "is_active": True},
            )
            template = PermissionTemplate.objects.filter(key=role_key).first()
            perm_keys = set(template.permission_keys if template else [])
            if username == "Demotest3":
                perm_keys |= all_permission_keys
            for key in sorted(perm_keys):
                permission = PermissionNode.objects.filter(key=key).first()
                if not permission:
                    continue
                UserPermissionOverride.objects.update_or_create(
                    user=user,
                    seller=getattr(user, "seller", None),
                    permission=permission,
                    defaults={"effect": UserPermissionOverride.EFFECT_ALLOW, "note": "Demotest3 enterprise demo"},
                )

    def _seed_enterprise_ui(self, users):
        ThemeConfig.objects.update_or_create(
            key="demotest3_glass_enterprise",
            defaults={
                "name": "Demotest3 Glass Enterprise",
                "brand_name": "Billentra Enterprise Demo",
                "primary": "#0F766E",
                "secondary": "#2563EB",
                "accent": "#F59E0B",
                "surface": "#F8FAFC",
                "dark_surface": "#07111F",
                "radius": 10,
                "density": "comfortable",
                "typography": {"display": "Inter", "body": "Inter"},
                "platform_overrides": {
                    "pos": {"density": "touch", "radius": 12},
                    "kiosk": {"density": "large-touch", "radius": 16},
                },
                "is_default": True,
                "is_active": True,
            },
        )

        module_specs = [
            ("ai_copilot", "AI Copilot", "auto_awesome", "#7C3AED", "/api/v1/ai/", "/ai", ["web", "app", "api"], 5),
            ("workspace_switcher", "Workspace Switcher", "workspace_premium", "#14B8A6", "/api/dashboard/", "/workspaces", ["web", "app"], 6),
            ("kiosk", "Kiosk", "scan-line", "#8B5CF6", "/pos/self-checkout/", "/kiosk", ["kiosk", "app", "web"], 35),
        ]
        for key, name, icon, color, api, route, platforms, order in module_specs:
            DynamicModule.objects.update_or_create(
                key=key,
                defaults={
                    "name": name,
                    "icon": icon,
                    "color": color,
                    "web_url": api,
                    "app_route": route,
                    "api_namespace": api,
                    "access_platforms": platforms,
                    "required_permissions": ["dashboard_view"],
                    "order": order,
                    "is_core": False,
                    "is_enabled": True,
                    "settings": {"demo": True, "instant_sync": True},
                },
            )

        workspace_widgets = {
            "admin_workspace": [
                ("admin_users", "Active Users", "metric", "dashboard_view", "14 roles live", "#14B8A6"),
                ("admin_permissions", "Permission Matrix", "status", "dashboard_view", "All synced", "#2563EB"),
                ("admin_realtime", "Realtime Control", "insight", "dashboard_view", "WebSocket ready", "#F59E0B"),
            ],
            "pos_workspace": [
                ("pos_sales", "POS Sales Today", "metric", "pos_view", "Rs 86,420", "#10B981"),
                ("pos_scanner", "Barcode Lane", "status", "pos_view", "6 scans/min", "#2563EB"),
                ("pos_print", "Thermal Printer", "status", "pos_print", "Ready", "#F59E0B"),
            ],
            "vendor_workspace": [
                ("vendor_orders", "Store Orders", "metric", "ecommerce_view", "38 open", "#EC4899"),
                ("vendor_revenue", "Marketplace Revenue", "chart", "analytics_view", "Rs 4.8L", "#10B981"),
            ],
            "crm_workspace": [
                ("crm_leads", "CRM Leads", "metric", "crm_view", "27 active", "#0EA5E9"),
                ("crm_followups", "Follow-ups", "table", "crm_view", "9 due", "#F59E0B"),
            ],
            "supplier_workspace": [
                ("supplier_pos", "Supply Orders", "metric", "suppliers_view", "12 POs", "#64748B"),
                ("supplier_payments", "Payment Tracking", "status", "billing_view", "Rs 1.2L due", "#EF4444"),
            ],
            "customer_workspace": [
                ("customer_orders", "My Orders", "metric", "orders_view", "5 recent", "#EC4899"),
                ("customer_wallet", "Wallet", "status", "billing_view", "Rs 4,200", "#10B981"),
            ],
            "kiosk_workspace": [
                ("kiosk_scans", "Kiosk Scans", "metric", "selfcheckout_view", "112 today", "#8B5CF6"),
                ("kiosk_qr", "QR Payments", "status", "billing_create", "UPI ready", "#10B981"),
            ],
        }
        for workspace_key, widgets in workspace_widgets.items():
            workspace = Workspace.objects.filter(key=workspace_key).first()
            if not workspace:
                continue
            for order, (key, title, widget_type, permission_key, value, accent) in enumerate(widgets, start=1):
                DashboardWidget.objects.update_or_create(
                    workspace=workspace,
                    key=key,
                    defaults={
                        "title": title,
                        "widget_type": widget_type,
                        "permission_key": permission_key,
                        "data_source": value,
                        "config": {"demo_value": value, "accent": accent, "animated": True},
                        "order": order * 10,
                        "is_enabled": True,
                    },
                )

        for username, user in users.items():
            workspace = Workspace.objects.filter(key=DEMO_USERS[username]["workspace"]).first()
            role = RoleTemplate.objects.filter(key=DEMO_USERS[username]["role"]).first()
            UserWorkspace.objects.update_or_create(
                user=user,
                defaults={
                    "workspace": workspace,
                    "role": role,
                    "platform_overrides": {"demo_modes": ["mobile", "tablet", "desktop", "pos", "kiosk"]},
                    "module_overrides": {"workspace_switching": username == "Demotest3"},
                    "dashboard_overrides": {"animated_kpis": True, "glass_theme": True},
                },
            )

    def _seed_warehouse(self):
        warehouse, _ = CommerceWarehouse.objects.update_or_create(
            name="Demotest3 Fulfillment Hub",
            defaults={"location": "Noida Sector 62", "capacity": 25000},
        )
        return warehouse

    def _seed_vendor(self, vendor_user, warehouse):
        vendor, _ = Vendor.objects.update_or_create(
            owner=vendor_user,
            defaults={
                "name": "Demotest3 Marketplace",
                "subdomain": "demotest3",
                "is_active": True,
                "primary_warehouse": None,
            },
        )
        VendorStoreSettings.objects.update_or_create(
            vendor=vendor,
            defaults={
                "support_email": "support@demotest3.example.com",
                "support_phone": "9000000399",
                "city": "Noida",
                "state": "UP",
                "country": "India",
                "settings_json": {"theme": "enterprise-glass", "demo_checkout": True},
            },
        )
        VendorMembership.objects.update_or_create(
            vendor=vendor,
            user=vendor_user,
            defaults={"role": VendorMembership.Role.OWNER, "department": "Marketplace", "is_active": True},
        )
        try:
            VendorWarehouse.objects.get_or_create(vendor=vendor, warehouse=warehouse, defaults={"is_active": True})
        except Exception:
            pass
        return vendor

    def _seed_products(self, owner, warehouse):
        products = []
        category_cache = {}
        for sku, name, category_name, price, stock, gst in PRODUCTS:
            category = category_cache.get(category_name)
            if not category:
                category, _ = Category.objects.get_or_create(owner=owner, name=category_name, defaults={"description": "Demotest3 enterprise demo category"})
                category_cache[category_name] = category
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "owner": owner,
                    "name": name,
                    "category": category,
                    "price": Decimal(price),
                    "stock": stock,
                    "min_stock": 5,
                    "unit": "pcs",
                    "gst_rate": Decimal(str(gst)),
                    "description": "Seeded enterprise demo product for POS, inventory, ecommerce, and reports.",
                },
            )
            Inventory.objects.update_or_create(owner=owner, product=product, defaults={"stock": stock})
            products.append(product)
        return products

    def _seed_parties(self, owner):
        parties = []
        for name, mobile, party_type, grade, score in CUSTOMERS + SUPPLIERS:
            party, _ = Party.objects.update_or_create(
                owner=owner,
                mobile=mobile,
                defaults={
                    "name": name,
                    "email": f"{mobile}@demotest3.example.com",
                    "address": "Demo Enterprise District, India",
                    "party_type": party_type,
                    "is_premium": True,
                    "credit_grade": grade,
                    "credit_score": score,
                    "customer_category": "Enterprise Demo",
                    "upi_id": f"{mobile}@upi",
                    "whatsapp_number": mobile,
                    "sms_number": mobile,
                    "is_active": True,
                },
            )
            parties.append(party)
        return parties

    def _seed_orders_invoices_payments(self, owner, parties, products, warehouse):
        today = timezone.localdate()
        for index, party in enumerate(parties):
            product_a = products[index % len(products)]
            product_b = products[(index + 2) % len(products)]
            order, _ = Order.objects.update_or_create(
                owner=owner,
                party=party,
                notes=f"Demotest3 {'purchase' if party.party_type == 'supplier' else 'sale'} workflow",
                defaults={
                    "warehouse": warehouse,
                    "placed_by": "user",
                    "status": "completed" if index % 2 == 0 else "pending",
                    "order_type": "PURCHASE" if party.party_type == "supplier" else "SALE",
                    "order_source": "Enterprise Demo",
                    "tax_percent": Decimal("18.00"),
                },
            )
            OrderItem.objects.update_or_create(
                order=order,
                product=product_a,
                defaults={"qty": 2 + index, "price": product_a.price, "tax_percent": product_a.gst_rate, "warehouse": warehouse},
            )
            OrderItem.objects.update_or_create(
                order=order,
                product=product_b,
                defaults={"qty": 1 + index, "price": product_b.price, "tax_percent": product_b.gst_rate, "warehouse": warehouse},
            )
            order.save()
            invoice, _ = Invoice.objects.update_or_create(
                order=order,
                defaults={
                    "amount": order.total_amount(),
                    "status": "paid" if index % 3 != 0 else "unpaid",
                    "gst_type": "GST",
                },
            )
            if invoice.status == "paid":
                Payment.objects.update_or_create(
                    invoice=invoice,
                    reference=f"DEMO-PAY-{invoice.id}",
                    defaults={"amount": invoice.amount, "method": "UPI", "note": "Demotest3 QR billing payment"},
                )
            Transaction.objects.update_or_create(
                party=party,
                order=order,
                defaults={
                    "txn_type": "credit" if party.party_type == "customer" else "debit",
                    "txn_mode": "upi",
                    "amount": invoice.amount,
                    "date": today,
                    "notes": "Demotest3 enterprise ledger transaction",
                },
            )

    def _seed_orders_invoices_payments_offline_safe(self, owner, parties, products, warehouse):
        post_save.disconnect(update_party_grade_and_notify, sender=Transaction)
        post_save.disconnect(_payment_event, sender=Payment)
        try:
            self._seed_orders_invoices_payments(owner, parties, products, warehouse)
        finally:
            post_save.connect(update_party_grade_and_notify, sender=Transaction)
            post_save.connect(_payment_event, sender=Payment)

    def _seed_crm(self, users):
        owner = users["Demotest3"]
        agent = users["Demotest3CRM"]
        statuses = [LocalShop.Status.NEW, LocalShop.Status.CONTACTED, LocalShop.Status.DEMO, LocalShop.Status.CONVERTED]
        for index, status in enumerate(statuses * 3, start=1):
            LocalShop.objects.update_or_create(
                owner=owner,
                mobile=f"988880{index:04d}",
                defaults={
                    "agent": agent,
                    "shop_name": f"Demo Retail Lead {index}",
                    "owner_name": f"Lead Owner {index}",
                    "category": ["Grocery", "Pharmacy", "Restaurant", "Electronics"][index % 4],
                    "status": status,
                    "referral_code": "DEMOTEST3",
                    "metadata": {
                        "deal_value": str(Decimal("25000.00") + Decimal(index * 3700)),
                        "source": "AI campaign",
                        "next_action": "Schedule demo" if status != LocalShop.Status.CONVERTED else "Onboard store",
                    },
                    "trial_expires_at": timezone.now() + timezone.timedelta(days=14 + index),
                },
            )

    def _seed_agent(self, users, parties):
        owner = users["Demotest3"]
        agent_user = users["Demotest3CRM"]
        agent, _ = FieldAgent.objects.update_or_create(
            user=agent_user,
            defaults={"owner": owner, "role": "staff", "mobile": agent_user.mobile, "is_active": True, "notes": "Demotest3 CRM and collection agent"},
        )
        agent.assigned_parties.set([p for p in parties if p.party_type == "customer"][:3])

    def _seed_audit_timeline(self, admin_user):
        events = [
            ("demo.roles.created", "Created dynamic roles for Admin, POS, Supplier, Vendor, CRM, Customer"),
            ("demo.permissions.assigned", "Assigned permission templates and per-user overrides"),
            ("demo.modules.enabled", "Enabled CRM, Billing, POS, Ecommerce, Supplier, Reports, Analytics"),
            ("demo.flutter.synced", "Flutter dashboard/menu/workspace config ready"),
            ("demo.realtime.ready", "Permission/module/dashboard websocket streams ready"),
        ]
        for action, target in events:
            AuditLog.objects.update_or_create(
                actor=admin_user,
                action=action,
                target=target,
                defaults={"platform": "demo", "metadata": {"user": "Demotest3", "premium_demo": True}},
            )
