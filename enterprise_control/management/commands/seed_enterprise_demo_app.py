from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from billing.models import Plan, PlanPermissions, Subscription
from commerce.models import Category, Invoice, Order, OrderItem, Payment, Product, Stock, Warehouse
from enterprise_control.models import APIRegistry, DashboardWidget, DynamicButton, DynamicMenuItem, DynamicModule, ThemeConfig, Workspace
from khataapp.models import Party, Transaction
from notifications.models import Notification


MODULES = [
    ("dashboard", "Dashboard", "grid", "#14b8a6", "/dashboard", 10),
    ("pos", "POS", "pos", "#38bdf8", "/pos", 20),
    ("billing", "Billing", "receipt", "#22c55e", "/billing", 30),
    ("crm", "CRM", "users", "#f97316", "/crm", 40),
    ("inventory", "Inventory", "boxes", "#a78bfa", "/inventory", 50),
    ("products", "Products", "tag", "#f59e0b", "/products", 60),
    ("reports", "Reports", "chart", "#fb7185", "/reports", 70),
    ("settings", "Settings", "settings", "#94a3b8", "/settings", 80),
    ("profile", "Profile", "user", "#2dd4bf", "/profile", 90),
    ("notifications", "Notifications", "bell", "#60a5fa", "/notifications", 100),
    ("devices", "Devices", "device", "#64748b", "/devices", 110),
]


class Command(BaseCommand):
    help = "Seed the complete live ERP demo used by the Vite/FastAPI enterprise app."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_enterprise_control")
        user = self._demo_user()
        plan = self._premium_plan()
        self._assign_plan(user, plan)
        modules = self._modules()
        workspace = self._workspace(modules)
        self._menu(workspace, modules)
        self._buttons(workspace, modules)
        self._widgets(workspace, modules)
        self._api_registry()
        self._business_data(user)
        self.stdout.write(self.style.SUCCESS("Enterprise demo app seed complete."))
        self.stdout.write("Demo login: Demotest3 / Demo@123")

    def _demo_user(self):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            email="demotest3@example.com",
            defaults={"username": "Demotest3", "is_active": True, "primary_role": "owner"},
        )
        user.username = "Demotest3"
        user.is_active = True
        user.primary_role = "owner"
        user.billing_access_level = "admin"
        user.billing_role_type = "vendor"
        user.permissions_json = self._permissions_blob()
        user.set_password("Demo@123")
        user.save()
        group, _ = Group.objects.get_or_create(name="Admin")
        user.groups.add(group)

        try:
            from accounts.models import UserProfile as AccountProfile
            from core_settings.models import CompanySettings

            company, _ = CompanySettings.objects.get_or_create(company_name="Demo Business")
            AccountProfile.objects.update_or_create(
                user=user,
                defaults={
                    "company": company,
                    "full_name": "Demo Test 3",
                    "mobile": "9999999999",
                    "business_name": "Demo Business",
                    "business_type": "Retail ERP",
                    "gst_number": "27ABCDE1234F1Z5",
                    "address": "Demo Business, Main Market",
                },
            )
        except Exception:
            pass

        try:
            from khataapp.models import UserProfile as KhataProfile

            KhataProfile.objects.update_or_create(
                user=user,
                defaults={
                    "full_name": "Demo Test 3",
                    "mobile": "9999999999",
                    "business_name": "Demo Business",
                    "business_type": "Retail ERP",
                    "gst_number": "27ABCDE1234F1Z5",
                    "address": "Demo Business, Main Market",
                    "created_from": "admin",
                },
            )
        except Exception:
            pass
        return user

    def _premium_plan(self):
        plan, _ = Plan.objects.update_or_create(
            slug="premium-plan-999",
            defaults={
                "name": "Premium Plan 999",
                "price": Decimal("999.00"),
                "price_monthly": Decimal("999.00"),
                "price_yearly": Decimal("9999.00"),
                "trial_days": 0,
                "description": "Premium ERP plan with POS, billing, CRM, inventory, reports, realtime dashboard, and app control center.",
                "active": True,
            },
        )
        PlanPermissions.objects.update_or_create(
            plan=plan,
            defaults={
                "allow_dashboard": True,
                "allow_reports": True,
                "allow_pdf_export": True,
                "allow_excel_export": True,
                "allow_add_party": True,
                "allow_edit_party": True,
                "allow_delete_party": True,
                "max_parties": 100000,
                "allow_add_transaction": True,
                "allow_edit_transaction": True,
                "allow_delete_transaction": True,
                "allow_bulk_transaction": True,
                "allow_commerce": True,
                "allow_warehouse": True,
                "allow_orders": True,
                "allow_inventory": True,
                "allow_whatsapp": True,
                "allow_sms": True,
                "allow_email": True,
                "allow_settings": True,
                "allow_users": True,
                "allow_api_access": True,
                "allow_ledger": True,
                "allow_credit_report": True,
                "allow_analytics": True,
            },
        )
        return plan

    def _assign_plan(self, user, plan):
        Subscription.objects.update_or_create(
            user=user,
            defaults={"plan": plan, "status": "active", "start_date": timezone.now(), "auto_renew": True},
        )
        for relation in ("account_userprofiles", "khata_userprofiles"):
            for profile in getattr(plan, relation).filter(user=user):
                profile.plan = plan
                profile.save(update_fields=["plan"])

    def _modules(self):
        result = {}
        for key, name, icon, color, route, order in MODULES:
            module, _ = DynamicModule.objects.update_or_create(
                key=key,
                defaults={
                    "name": name,
                    "icon": icon,
                    "color": color,
                    "web_url": route,
                    "app_route": route,
                    "api_namespace": "/api/system",
                    "access_platforms": ["web", "app", "desktop", "pos", "api"],
                    "required_permissions": [f"{key}_view"],
                    "order": order,
                    "is_core": True,
                    "is_enabled": True,
                },
            )
            result[key] = module
        ThemeConfig.objects.update_or_create(
            key="billentra_enterprise_dark",
            defaults={
                "name": "Billentra Enterprise Dark",
                "brand_name": "Billentra OS",
                "primary": "#14b8a6",
                "secondary": "#38bdf8",
                "accent": "#f59e0b",
                "surface": "#101827",
                "dark_surface": "#070b14",
                "radius": 8,
                "density": "comfortable",
                "is_default": True,
                "is_active": True,
            },
        )
        return result

    def _workspace(self, modules):
        workspace, _ = Workspace.objects.update_or_create(
            key="demo_business_enterprise",
            defaults={
                "name": "Demo Business Enterprise",
                "landing_route": "/dashboard",
                "platform": "app",
                "module_keys": list(modules.keys()),
                "menu_schema": [],
                "layout_schema": {"columns": 12, "density": "comfortable"},
                "is_default": True,
                "is_active": True,
                "order": 1,
            },
        )
        return workspace

    def _menu(self, workspace, modules):
        groups = [
            ("operations", "Operations", ["dashboard", "pos", "billing", "inventory", "products"]),
            ("growth", "Growth", ["crm", "reports", "notifications"]),
            ("control", "Control Center", ["settings", "profile", "devices"]),
        ]
        for order, (key, title, children) in enumerate(groups, start=1):
            parent, _ = DynamicMenuItem.objects.update_or_create(
                key=f"demo_{key}",
                defaults={
                    "title": title,
                    "workspace": workspace,
                    "icon": "folder",
                    "route": "",
                    "platform_access": ["web", "app", "desktop", "pos"],
                    "order": order * 100,
                    "is_group": True,
                    "is_enabled": True,
                },
            )
            for child_order, module_key in enumerate(children, start=1):
                module = modules[module_key]
                DynamicMenuItem.objects.update_or_create(
                    key=f"demo_{module_key}",
                    defaults={
                        "title": module.name,
                        "parent": parent,
                        "workspace": workspace,
                        "module": module,
                        "icon": module.icon,
                        "route": module.app_route,
                        "badge": "Live" if module_key in {"pos", "billing", "reports"} else "",
                        "color": module.color,
                        "permission_key": f"{module_key}_view",
                        "platform_access": ["web", "app", "desktop", "pos"],
                        "order": order * 100 + child_order,
                        "is_group": False,
                        "is_enabled": True,
                    },
                )

    def _buttons(self, workspace, modules):
        buttons = [
            ("open_pos", "Open POS", "Start billing from product cart", "pos", "/pos", "#38bdf8", True),
            ("create_invoice", "Create Invoice", "Generate GST invoice", "billing", "/billing", "#22c55e", True),
            ("add_customer", "Add Customer", "Create CRM lead or customer", "crm", "/crm", "#f97316", False),
            ("stock_report", "Stock Report", "Review inventory health", "reports", "/reports", "#fb7185", False),
        ]
        for order, (key, label, description, module_key, route, color, primary) in enumerate(buttons, start=1):
            DynamicButton.objects.update_or_create(
                key=key,
                defaults={
                    "label": label,
                    "description": description,
                    "module": modules[module_key],
                    "workspace": workspace,
                    "action_type": "module",
                    "route": route,
                    "icon": modules[module_key].icon,
                    "color": color,
                    "gradient": [color, "#0f172a"],
                    "shape": "rounded",
                    "permission_key": f"{module_key}_view",
                    "plan_keys": ["premium-plan-999"],
                    "platform_access": ["web", "app", "desktop", "pos"],
                    "order": order,
                    "is_primary": primary,
                    "is_enabled": True,
                },
            )

    def _widgets(self, workspace, modules):
        widgets = [
            ("revenue", "Revenue", "metric", "billing", 10),
            ("orders", "Orders", "metric", "billing", 20),
            ("top_products", "Top Products", "table", "products", 30),
            ("recent_invoices", "Recent Invoices", "table", "billing", 40),
            ("live_activity", "Live Activity", "status", "dashboard", 50),
        ]
        for key, title, kind, module_key, order in widgets:
            DashboardWidget.objects.update_or_create(
                workspace=workspace,
                key=key,
                defaults={
                    "title": title,
                    "widget_type": kind,
                    "module": modules[module_key],
                    "permission_key": f"{module_key}_view",
                    "data_source": "/api/system/live-data/",
                    "config": {"live": True},
                    "order": order,
                    "is_enabled": True,
                },
            )

    def _api_registry(self):
        apis = [
            ("System App Config", "/api/system/app-config/", "GET", "system", "active", ["web", "flutter", "pos"]),
            ("System Live Data", "/api/system/live-data/", "GET", "dashboard", "active", ["web", "flutter"]),
            ("API Status", "/api/system/api-status/", "GET", "settings", "active", ["web"]),
            ("Auth Login", "/auth/login", "POST", "auth", "active", ["web", "flutter", "pos"]),
            ("Menu Sidebar", "/menu/sidebar", "GET", "menu", "active", ["web", "flutter"]),
            ("Reports Catalog", "/reports/catalog", "GET", "reports", "active", ["web", "flutter"]),
            ("Offline POS Pull", "/offline/pull", "GET", "pos", "active", ["pos", "flutter"]),
        ]
        for name, endpoint, method, module, status, apps in apis:
            APIRegistry.objects.update_or_create(
                endpoint=endpoint,
                method=method,
                defaults={
                    "name": name,
                    "module": module,
                    "status": status,
                    "connected_apps": apps,
                    "permission_keys": [f"{module}_view"],
                    "version": "v1",
                    "auth_required": "login" not in endpoint,
                    "source": "seed",
                    "is_active": True,
                },
            )

    def _business_data(self, user):
        warehouse, _ = Warehouse.objects.get_or_create(name="Demo Main Warehouse", defaults={"location": "Demo Business", "capacity": 5000})
        categories = {}
        for name in ["Grocery", "Electronics", "Home Care", "Stationery"]:
            categories[name], _ = Category.objects.get_or_create(owner=user, name=name, defaults={"description": f"{name} demo category"})
        product_rows = [
            ("DEMO-RICE-25", "Premium Rice 25kg", "Grocery", "2299.00", 42, "18"),
            ("DEMO-OIL-5", "Cold Pressed Oil 5L", "Grocery", "899.00", 65, "5"),
            ("DEMO-LED-12", "Smart LED Bulb 12W", "Electronics", "249.00", 120, "18"),
            ("DEMO-CLEAN-1", "Surface Cleaner 1L", "Home Care", "179.00", 80, "18"),
            ("DEMO-NOTE-A4", "A4 Premium Notebook", "Stationery", "99.00", 220, "12"),
            ("DEMO-SCANNER", "USB Barcode Scanner", "Electronics", "1899.00", 14, "18"),
        ]
        products = []
        for sku, name, category, price, stock, gst in product_rows:
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "owner": user,
                    "name": name,
                    "category": categories[category],
                    "price": Decimal(price),
                    "stock": stock,
                    "min_stock": 10,
                    "description": f"Demo Brand | {name}",
                    "unit": "pcs",
                    "hsn_code": "9988",
                    "gst_rate": Decimal(gst),
                },
            )
            products.append(product)
            Stock.objects.update_or_create(product=product, warehouse=warehouse, defaults={"quantity": stock})

        parties = []
        party_rows = [
            ("Aarav Retail", "customer", "9000001001", "A", "1200.00"),
            ("Nisha Traders", "customer", "9000001002", "B", "0.00"),
            ("Metro Supplies", "supplier", "9000001003", "A+", "4500.00"),
            ("Quick Mart", "customer", "9000001004", "A", "750.00"),
        ]
        for name, party_type, mobile, grade, due in party_rows:
            party, _ = Party.objects.update_or_create(
                owner=user,
                mobile=mobile,
                defaults={
                    "name": name,
                    "party_type": party_type,
                    "email": f"{mobile}@demo.local",
                    "address": "Demo Market",
                    "credit_grade": grade,
                    "credit_score": 82 if grade.startswith("A") else 68,
                    "total_due": Decimal(due),
                    "is_active": True,
                },
            )
            parties.append(party)

        for index, party in enumerate(parties[:3], start=1):
            order, _ = Order.objects.get_or_create(
                owner=user,
                party=party,
                invoice_number=f"DEMO-PO-{index:03d}",
                defaults={
                    "warehouse": warehouse,
                    "placed_by": "user",
                    "status": "completed",
                    "order_type": "SALE",
                    "tax_percent": Decimal("18.00"),
                    "order_source": "Demo POS",
                },
            )
            for product in products[index - 1 : index + 1]:
                OrderItem.objects.update_or_create(
                    order=order,
                    product=product,
                    defaults={"qty": index + 1, "price": product.price, "tax_percent": product.gst_rate, "warehouse": warehouse},
                )
            order.save()
            invoice, _ = Invoice.objects.update_or_create(
                order=order,
                defaults={
                    "amount": order.total_amount(),
                    "status": "paid" if index < 3 else "unpaid",
                    "gst_type": "GST",
                },
            )
            if invoice.status == "paid":
                Payment.objects.get_or_create(
                    invoice=invoice,
                    reference=f"DEMO-PAY-{index:03d}",
                    defaults={"amount": invoice.amount, "method": "UPI", "note": "Demo payment"},
                )
            Transaction.objects.get_or_create(
                party=party,
                invoice=invoice,
                created_by=user,
                defaults={
                    "txn_type": "credit",
                    "txn_mode": "upi",
                    "amount": invoice.amount,
                    "date": timezone.localdate(),
                    "notes": f"Invoice {invoice.number}",
                    "order": order,
                },
            )

        notes = [
            ("POS ready", "Barcode cart, billing, payment, and receipt are connected to live product data.", "success"),
            ("Premium plan active", "Demo Test 3 is running on Premium Plan 999.", "info"),
            ("Stock alert", "USB Barcode Scanner is near reorder threshold.", "warning"),
        ]
        for title, body, level in notes:
            Notification.objects.get_or_create(user=user, title=title, defaults={"body": body, "level": level})

    def _permissions_blob(self):
        blob = {}
        for key, *_ in MODULES:
            for action in ("view", "create", "edit", "delete", "export", "print", "approve", "manage"):
                blob[f"{key}_{action}"] = True
        for key in ("web_access", "app_access", "pos_access", "kiosk_access", "api_access"):
            blob[key] = True
        return blob
