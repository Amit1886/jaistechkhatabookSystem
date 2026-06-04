from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from jaistech_erp.models import (
    Business,
    Customer,
    Expense,
    Invoice,
    InvoiceLine,
    LedgerAccount,
    LedgerEntry,
    Module,
    Permission,
    Product,
    Role,
    Store,
    UserBusinessMembership,
)


MODULES = [
    ("dashboard", "Dashboard", "layout-dashboard", "#176B87"),
    ("products", "Products", "package", "#2D9CDB"),
    ("sales", "Sales", "receipt", "#27AE60"),
    ("purchases", "Purchases", "shopping-bag", "#9B51E0"),
    ("inventory", "Inventory", "warehouse", "#F2994A"),
    ("pos", "POS", "scan-barcode", "#EB5757"),
    ("crm", "CRM", "users", "#00A3A3"),
    ("hrm", "HRM", "briefcase", "#6B7280"),
    ("payroll", "Payroll", "wallet", "#475569"),
    ("projects", "Projects", "kanban", "#0F766E"),
    ("tasks", "Tasks", "check-square", "#7C3AED"),
    ("reports", "Reports", "bar-chart", "#2563EB"),
    ("stores", "Multi Store", "store", "#0891B2"),
    ("loyalty", "Loyalty", "badge-percent", "#DB2777"),
    ("self_checkout", "Self Checkout", "qr-code", "#16A34A"),
    ("ecommerce", "eCommerce", "globe", "#EA580C"),
    ("accounting", "Accounting", "landmark", "#334155"),
    ("expenses", "Expenses", "credit-card", "#B45309"),
    ("assets", "Assets", "boxes", "#4B5563"),
    ("support", "Support", "headphones", "#0284C7"),
]


class Command(BaseCommand):
    help = "Seed JaisTech ERP modules, demo company, live demo records, and role permissions."

    def handle(self, *args, **options):
        User = get_user_model()
        user, _ = User.objects.update_or_create(
            mobile="9999999999",
            defaults={
                "email": "demo.test3@jaistech.local",
                "username": "Demo Test 3",
                "is_staff": True,
                "is_active": True,
                "primary_role": "owner",
            },
        )
        user.set_password("Demo@12345")
        user.save()

        business, _ = Business.objects.update_or_create(
            name="Demo Business",
            defaults={"mobile": "9999999999", "email": "demo@jaistech.local", "gst_number": "29ABCDE1234F1Z5"},
        )
        main_store, _ = Store.objects.update_or_create(business=business, code="main", defaults={"name": "Main Store", "is_default": True})
        online_store, _ = Store.objects.update_or_create(business=business, code="online", defaults={"name": "Online Store", "store_type": "ecommerce"})

        created_modules = []
        for order, (key, name, icon, color) in enumerate(MODULES, start=1):
            module, _ = Module.objects.update_or_create(
                key=key,
                defaults={"name": name, "icon": icon, "color": color, "order": order, "is_core": True, "is_enabled": True},
            )
            created_modules.append(module)
            for action, label in Permission.ACTIONS:
                Permission.objects.get_or_create(
                    module=module,
                    action=action,
                    defaults={"key": f"{key}_{action}", "label": f"{name} {label}"},
                )

        owner_role, _ = Role.objects.update_or_create(
            business=business,
            key="owner",
            defaults={"name": "Owner", "description": "Full business access", "is_admin": True, "is_system": True},
        )
        owner_role.permissions.set(Permission.objects.all())
        membership, _ = UserBusinessMembership.objects.update_or_create(user=user, business=business, defaults={"role": owner_role, "is_active": True})
        membership.stores.set([main_store, online_store])

        products = [
            ("JT-POS-001", "Thermal Billing Roll", "Stationery", "75.00", "42.00", "120"),
            ("JT-INV-002", "Barcode Label Pack", "Inventory", "180.00", "95.00", "45"),
            ("JT-CRM-003", "Premium Support Plan", "Services", "1499.00", "0.00", "999"),
            ("JT-GST-004", "GST Invoice Book", "Accounting", "220.00", "110.00", "8"),
            ("JT-SC-005", "Self Checkout QR Stand", "POS", "699.00", "360.00", "4"),
        ]
        product_objs = []
        for sku, name, cat, sale, purchase, stock in products:
            obj, _ = Product.objects.update_or_create(
                business=business,
                sku=sku,
                defaults={
                    "barcode": sku.replace("-", ""),
                    "name": name,
                    "category": cat,
                    "sale_price": Decimal(sale),
                    "purchase_price": Decimal(purchase),
                    "tax_rate": Decimal("18.00"),
                    "stock_qty": Decimal(stock),
                    "low_stock_qty": Decimal("10.00"),
                },
            )
            product_objs.append(obj)

        customers = []
        for name, mobile in [("Anita Retail", "9888888881"), ("B2B Mart", "9888888882"), ("Walk-in Customer", "9999999999")]:
            cust, _ = Customer.objects.update_or_create(business=business, mobile=mobile, defaults={"name": name, "loyalty_points": 120})
            customers.append(cust)

        for index, customer in enumerate(customers, start=1):
            invoice, _ = Invoice.objects.update_or_create(
                invoice_number=f"JT-INV-2026-00{index}",
                defaults={"business": business, "store": main_store, "customer": customer, "payment_method": "upi", "channel": "pos"},
            )
            if not invoice.lines.exists():
                for product in product_objs[:2]:
                    InvoiceLine.objects.create(
                        invoice=invoice,
                        product=product,
                        description=product.name,
                        quantity=Decimal("2"),
                        unit_price=product.sale_price,
                        tax_rate=product.tax_rate,
                    )
                invoice.recalculate()
                invoice.save(update_fields=["subtotal", "tax_total", "grand_total"])

        Expense.objects.update_or_create(
            expense_number="JT-EXP-2026-001",
            defaults={"business": business, "store": main_store, "category": "Rent", "vendor_name": "Demo Plaza", "amount": Decimal("18000.00"), "tax_amount": Decimal("3240.00")},
        )
        Expense.objects.update_or_create(
            expense_number="JT-EXP-2026-002",
            defaults={"business": business, "store": online_store, "category": "Marketing", "vendor_name": "Ad Network", "amount": Decimal("4200.00"), "tax_amount": Decimal("756.00")},
        )

        cash, _ = LedgerAccount.objects.update_or_create(business=business, code="1000", defaults={"name": "Cash", "account_type": "asset"})
        sales, _ = LedgerAccount.objects.update_or_create(business=business, code="4000", defaults={"name": "Sales", "account_type": "income"})
        LedgerEntry.objects.get_or_create(business=business, account=cash, reference="OPENING", defaults={"debit": Decimal("50000.00"), "memo": "Opening cash balance"})
        LedgerEntry.objects.get_or_create(business=business, account=sales, reference="JT-INV-2026-001", defaults={"credit": Decimal("885.00"), "memo": "Demo POS sale"})

        self.stdout.write(self.style.SUCCESS("Seeded JaisTech ERP demo data. Login: demo.test3@jaistech.local / Demo@12345"))

