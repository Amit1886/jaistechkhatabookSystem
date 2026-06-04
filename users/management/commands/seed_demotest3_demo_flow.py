from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models.signals import post_save
from django.utils import timezone

from accounts.models import UserProfile as AccountUserProfile
from ai_engine.models import CustomerRiskScore, ProductDemandForecast, SalesmanScore
from ai_engine.services.runner import run_all_ai_engines
from billing.models import BillingInvoice, FeatureRegistry, Plan, PlanFeature, Subscription, SubscriptionHistory
from billing.services import sync_feature_registry
from commerce.models import (
    Category as CommerceCategory,
    Invoice as CommerceInvoice,
    Notification as CommerceNotification,
    Order as CommerceOrder,
    OrderItem as CommerceOrderItem,
    Payment as CommercePayment,
    Product as CommerceProduct,
    SalesVoucher,
    SalesVoucherItem,
    Warehouse as CommerceWarehouse,
)
from commission.models import CommissionPayout, CommissionRule
from core_settings.models import AppSettings, CompanySettings, SettingDefinition, SettingValue, UISettings
from core_settings.services import sync_settings_registry
from delivery.models import DeliveryAssignment, DeliveryTrackingPing
from khataapp.models import (
    CompanySettings as KhataCompanySettings,
    OfflineMessage,
    Party,
    ReminderLog,
    SupplierPayment,
    Transaction as KhataTransaction,
    UserProfile as KhataUserProfile,
    auto_create_login_link,
    compute_credit_grade,
)
from khataapp.utils.credit_report import generate_credit_report_pdf, generate_credit_report_pdf_for_party
from orders.models import Order as UnifiedOrder
from orders.models import OrderItem as UnifiedOrderItem
from orders.models import POSBill
from payments.models import DailyCashSummary, PaymentTransaction
from printer_config.models import (
    PrintDocumentType,
    PrintMode,
    PrintPaperSize,
    PrintRenderLog,
    PrintTemplate,
    PrinterConfig,
    UserPrintTemplate,
)
from printer_config.services.context_builder import build_dummy_context
from printer_config.services.template_renderer import render_template_payload
from products.models import Category as UnifiedCategory
from products.models import Product as UnifiedProduct
from products.models import ProductPriceRule, WarehouseInventory
from scanner_config.models import ScanEvent, ScannerConfig
from system_mode.models import SystemMode
from users.models import UserProfileExt, UserRole
from warehouse.models import Warehouse as UnifiedWarehouse
from warehouse.models import WarehouseStaffAssignment


ONE_BY_ONE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2p3cQAAAAASUVORK5CYII="
)


@dataclass
class DemoUsers:
    admin: object
    owner: object
    customer: object
    supplier: object
    vendor: object
    staff: object
    salesman: object
    delivery: object
    risk_low: object
    risk_medium: object
    risk_high: object


class Command(BaseCommand):
    help = "Create complete end-to-end demo dataset and client demo report for user Demotest3."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="Demotest3", help="Demo owner username")
        parser.add_argument("--password", default="Demo@123", help="Password for demo users")
        parser.add_argument(
            "--output-dir",
            default="demo_outputs",
            help="Directory where generated demo report files are written",
        )

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        output_dir = Path(options["output_dir"])

        self.stdout.write(self.style.NOTICE(f"Seeding full demo flow for: {username}"))
        sync_feature_registry()
        sync_settings_registry()

        users = self._seed_users(username=username, password=password)
        plans = self._seed_plans_and_features(owner=users.owner)
        settings_payload = self._seed_branding_and_settings(owner=users.owner, plan=plans["premium"], admin=users.admin)
        stock_payload = self._seed_products_and_warehouses(users=users)
        party_payload = self._seed_parties_and_transactions(users=users, stock_payload=stock_payload)
        commerce_payload = self._seed_commerce_documents(users=users, party_payload=party_payload)
        ai_payload = self._seed_unified_orders_and_ai(users=users, stock_payload=stock_payload)
        print_payload = self._seed_print_and_scanner(users=users, commerce_payload=commerce_payload)
        notification_payload = self._seed_notifications(users=users, party_payload=party_payload, commerce_payload=commerce_payload)
        crud_payload = self._run_crud_validation(owner=users.owner)
        payment_links = self._build_payment_links(
            party_payload=party_payload,
            commerce_payload=commerce_payload,
            profile=settings_payload["khata_profile"],
        )

        site = Site.objects.get_current()
        site.domain = "demotest3.jaistech.demo"
        site.name = "Demotest3 White Label Demo"
        site.save(update_fields=["domain", "name"])

        mode = SystemMode.get_solo()
        mode.current_mode = SystemMode.Mode.DESKTOP
        mode.is_locked = False
        mode.updated_by = users.admin
        mode.save()

        dataset = self._build_dataset(
            users=users,
            plans=plans,
            settings_payload=settings_payload,
            party_payload=party_payload,
            commerce_payload=commerce_payload,
            ai_payload=ai_payload,
            print_payload=print_payload,
            payment_links=payment_links,
            notification_payload=notification_payload,
            crud_payload=crud_payload,
            output_dir=output_dir,
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        self._write_credit_reports(output_dir=output_dir, parties=party_payload["parties"])
        self._write_dataset_json(dataset=dataset, output_dir=output_dir)
        self._write_demo_markdown(dataset=dataset, output_dir=output_dir)

        self.stdout.write(self.style.SUCCESS("Demo flow seed completed successfully."))
        self.stdout.write(self.style.SUCCESS(f"JSON: {output_dir / 'demotest3_demo_dataset.json'}"))
        self.stdout.write(self.style.SUCCESS(f"MARKDOWN: {output_dir / 'DEMOTEST3_E2E_DEMO_FLOW.md'}"))

    def _upsert_user(
        self,
        *,
        email: str,
        username: str,
        password: str,
        mobile: str | None = None,
        is_staff: bool = False,
        is_superuser: bool = False,
    ):
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first() or User.objects.filter(username=username).first()
        if not user:
            user = User(
                email=email,
                username=username,
                mobile=mobile,
                is_staff=is_staff,
                is_superuser=is_superuser,
                is_active=True,
                is_otp_verified=True,
            )
            user.set_password(password)
            user.save()
            return user

        updates = []
        if user.username != username:
            user.username = username
            updates.append("username")
        if mobile and not get_user_model().objects.exclude(pk=user.pk).filter(mobile=mobile).exists():
            if user.mobile != mobile:
                user.mobile = mobile
                updates.append("mobile")
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            updates.append("is_staff")
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            updates.append("is_superuser")
        if not user.is_active:
            user.is_active = True
            updates.append("is_active")
        if not user.is_otp_verified:
            user.is_otp_verified = True
            updates.append("is_otp_verified")
        if updates:
            user.save(update_fields=updates)
        user.set_password(password)
        user.save(update_fields=["password"])
        return user

    def _ensure_groups(self):
        group_names = ["Customer", "Supplier", "Vendor", "Staff", "Admin"]
        groups = {}
        for name in group_names:
            groups[name], _ = Group.objects.get_or_create(name=name)
        return groups

    def _assign_group(self, user, *group_names: str):
        groups = Group.objects.filter(name__in=group_names)
        user.groups.set(groups)

    def _set_saas_profile(self, *, user, role: str, wallet="0", credit="0", commission="0", is_staff=False):
        profile, _ = UserProfileExt.objects.get_or_create(user=user)
        profile.role = role
        profile.wallet_balance = Decimal(wallet)
        profile.credit_balance = Decimal(credit)
        profile.commission_earned = Decimal(commission)
        profile.is_active_staff = is_staff
        profile.printer_preferences = {
            "default_paper": "pos_80",
            "auto_print": True,
            "quick_print_button": True,
        }
        profile.scanner_preferences = {
            "default_scanner": "usb_hid",
            "auto_submit": True,
            "sound_enabled": True,
        }
        profile.pos_layout_preferences = {
            "pc": {"dense_rows": True, "shortcut_bar": True},
            "tablet": {"touch_mode": True},
            "mobile": {"step_mode": True},
        }
        profile.save()

    def _seed_users(self, *, username: str, password: str) -> DemoUsers:
        self._ensure_groups()

        admin = self._upsert_user(
            email="admin@jaistech.demo",
            username="DemoAdmin",
            password=password,
            mobile="9000000001",
            is_staff=True,
            is_superuser=True,
        )
        owner = self._upsert_user(
            email="demotest3@gmail.com",
            username=username,
            password=password,
            mobile="9000000033",
            is_staff=True,
            is_superuser=False,
        )
        customer = self._upsert_user(
            email="customer.demo@jaistech.demo",
            username="DemoCustomer",
            password=password,
            mobile="9000000034",
        )
        supplier = self._upsert_user(
            email="supplier.demo@jaistech.demo",
            username="DemoSupplier",
            password=password,
            mobile="9000000035",
        )
        vendor = self._upsert_user(
            email="vendor.demo@jaistech.demo",
            username="DemoVendor",
            password=password,
            mobile="9000000036",
        )
        staff = self._upsert_user(
            email="staff.demo@jaistech.demo",
            username="DemoStaff",
            password=password,
            mobile="9000000037",
        )
        salesman = self._upsert_user(
            email="salesman.demo@jaistech.demo",
            username="DemoSalesman",
            password=password,
            mobile="9000000038",
        )
        delivery = self._upsert_user(
            email="delivery.demo@jaistech.demo",
            username="DemoDelivery",
            password=password,
            mobile="9000000039",
        )
        risk_low = self._upsert_user(
            email="risk.low@jaistech.demo",
            username="RiskLow",
            password=password,
            mobile="9000000040",
        )
        risk_medium = self._upsert_user(
            email="risk.medium@jaistech.demo",
            username="RiskMedium",
            password=password,
            mobile="9000000041",
        )
        risk_high = self._upsert_user(
            email="risk.high@jaistech.demo",
            username="RiskHigh",
            password=password,
            mobile="9000000042",
        )

        self._assign_group(admin, "Admin")
        self._assign_group(owner, "Admin", "Staff")
        self._assign_group(customer, "Customer")
        self._assign_group(supplier, "Supplier")
        self._assign_group(vendor, "Vendor")
        self._assign_group(staff, "Staff")
        self._assign_group(salesman, "Staff")
        self._assign_group(delivery, "Staff")
        self._assign_group(risk_low, "Customer")
        self._assign_group(risk_medium, "Customer")
        self._assign_group(risk_high, "Customer")

        self._set_saas_profile(user=owner, role=UserRole.ADMIN, wallet="25000", credit="75000", commission="1200", is_staff=True)
        self._set_saas_profile(user=customer, role=UserRole.B2C_CUSTOMER, wallet="1200", credit="0", commission="0")
        self._set_saas_profile(user=supplier, role=UserRole.B2B_CUSTOMER, wallet="0", credit="25000", commission="0")
        self._set_saas_profile(user=vendor, role=UserRole.WAREHOUSE_STAFF, wallet="0", credit="0", commission="0", is_staff=True)
        self._set_saas_profile(user=staff, role=UserRole.POS_CASHIER, wallet="0", credit="0", commission="0", is_staff=True)
        self._set_saas_profile(user=salesman, role=UserRole.SALESMAN, wallet="0", credit="0", commission="0", is_staff=True)
        self._set_saas_profile(user=delivery, role=UserRole.DELIVERY_PARTNER, wallet="0", credit="0", commission="0", is_staff=True)
        self._set_saas_profile(user=risk_low, role=UserRole.B2C_CUSTOMER, wallet="0", credit="0", commission="0")
        self._set_saas_profile(user=risk_medium, role=UserRole.B2C_CUSTOMER, wallet="0", credit="0", commission="0")
        self._set_saas_profile(user=risk_high, role=UserRole.B2B_CUSTOMER, wallet="0", credit="0", commission="0")

        # Billing Model Hierarchy demo values (visible in Profile + Demo Center)
        try:
            from billing.hierarchy import apply_billing_defaults_to_user

            owner.billing_access_level = "user"
            owner.billing_role_type = "vendor"
            owner.billing_child_role = "shop_manager"
            apply_billing_defaults_to_user(owner, overwrite=False)
            # Link all demo users under the owner (one billing profile manages all)
            for u in (customer, supplier, vendor, staff, salesman, delivery, risk_low, risk_medium, risk_high):
                try:
                    u.parent = owner
                except Exception:
                    pass
            owner.save(
                update_fields=[
                    "billing_access_level",
                    "billing_role_type",
                    "billing_child_role",
                    "permissions_json",
                ]
            )

            customer.billing_access_level = ""
            customer.billing_role_type = "customer"
            customer.billing_child_role = "authorized_user"
            apply_billing_defaults_to_user(customer, overwrite=False)
            customer.save(update_fields=["parent", "billing_access_level", "billing_role_type", "billing_child_role", "permissions_json"])

            supplier.billing_access_level = ""
            supplier.billing_role_type = "supplier"
            supplier.billing_child_role = "purchase_manager"
            apply_billing_defaults_to_user(supplier, overwrite=False)
            supplier.save(update_fields=["parent", "billing_access_level", "billing_role_type", "billing_child_role", "permissions_json"])

            vendor.billing_access_level = ""
            vendor.billing_role_type = "vendor"
            vendor.billing_child_role = "inventory_manager"
            apply_billing_defaults_to_user(vendor, overwrite=False)
            vendor.save(update_fields=["parent", "billing_access_level", "billing_role_type", "billing_child_role", "permissions_json"])

            staff.billing_access_level = ""
            staff.billing_role_type = "sub_user"
            staff.billing_child_role = "data_entry"
            apply_billing_defaults_to_user(staff, overwrite=False)
            staff.save(update_fields=["parent", "billing_access_level", "billing_role_type", "billing_child_role", "permissions_json"])

            delivery.billing_access_level = ""
            delivery.billing_role_type = "field_agent"
            delivery.billing_child_role = "field_executive"
            apply_billing_defaults_to_user(delivery, overwrite=False)
            delivery.save(update_fields=["parent", "billing_access_level", "billing_role_type", "billing_child_role", "permissions_json"])
        except Exception:
            pass

        return DemoUsers(
            admin=admin,
            owner=owner,
            customer=customer,
            supplier=supplier,
            vendor=vendor,
            staff=staff,
            salesman=salesman,
            delivery=delivery,
            risk_low=risk_low,
            risk_medium=risk_medium,
            risk_high=risk_high,
        )

    def _ensure_plan(self, *, name, slug, monthly, yearly, price, description, trial_days=0):
        plan, created = Plan.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "price_monthly": Decimal(monthly),
                "price_yearly": Decimal(yearly),
                "price": Decimal(price),
                "description": description,
                "trial_days": trial_days,
                "active": True,
            },
        )
        if not created:
            plan.name = name
            plan.price_monthly = Decimal(monthly)
            plan.price_yearly = Decimal(yearly)
            plan.price = Decimal(price)
            plan.description = description
            plan.trial_days = trial_days
            plan.active = True
            plan.save()
        plan.get_permissions()
        return plan

    def _seed_plans_and_features(self, *, owner):
        free = self._ensure_plan(
            name="Free Plan",
            slug="free-plan",
            monthly="0.00",
            yearly="0.00",
            price="0.00",
            description="Entry plan for onboarding demo",
            trial_days=0,
        )
        basic = self._ensure_plan(
            name="Basic Plan",
            slug="basic-plan",
            monthly="499.00",
            yearly="4999.00",
            price="499.00",
            description="Basic automation and invoicing",
            trial_days=7,
        )
        premium = self._ensure_plan(
            name="Premium Plan",
            slug="premium-plan",
            monthly="999.00",
            yearly="9999.00",
            price="999.00",
            description="Full feature set for growth and automation",
            trial_days=14,
        )

        free_perm = free.get_permissions()
        free_perm.allow_whatsapp = False
        free_perm.allow_pdf_export = False
        free_perm.allow_credit_report = False
        free_perm.allow_api_access = False
        free_perm.allow_commerce = False
        free_perm.allow_orders = False
        free_perm.allow_inventory = False
        free_perm.max_parties = 25
        free_perm.save()

        basic_perm = basic.get_permissions()
        basic_perm.allow_whatsapp = True
        basic_perm.allow_pdf_export = True
        basic_perm.allow_credit_report = True
        basic_perm.allow_commerce = True
        basic_perm.allow_orders = True
        basic_perm.allow_inventory = True
        basic_perm.allow_api_access = False
        basic_perm.max_parties = 250
        basic_perm.save()

        premium_perm = premium.get_permissions()
        premium_perm.allow_whatsapp = True
        premium_perm.allow_pdf_export = True
        premium_perm.allow_credit_report = True
        premium_perm.allow_commerce = True
        premium_perm.allow_orders = True
        premium_perm.allow_inventory = True
        premium_perm.allow_api_access = True
        premium_perm.allow_analytics = True
        premium_perm.allow_bulk_transaction = True
        premium_perm.max_parties = 5000
        premium_perm.save()

        custom_feature_keys = {
            "reports.pdf_export": "PDF Export",
            "payments.link": "Payment Link",
            "credit.report": "Credit Report",
            "template.editor": "Template Editor",
        }
        for key, label in custom_feature_keys.items():
            FeatureRegistry.objects.update_or_create(
                key=key,
                defaults={
                    "label": label,
                    "group": "Advanced",
                    "description": f"{label} feature toggle",
                    "active": True,
                },
            )

        feature_matrix = {
            free.slug: {
                "communication.whatsapp": False,
                "reports.pdf_export": False,
                "payments.link": False,
                "credit.report": False,
                "template.editor": False,
            },
            basic.slug: {
                "communication.whatsapp": True,
                "reports.pdf_export": True,
                "payments.link": True,
                "credit.report": True,
                "template.editor": False,
            },
            premium.slug: {
                "communication.whatsapp": True,
                "reports.pdf_export": True,
                "payments.link": True,
                "credit.report": True,
                "template.editor": True,
            },
        }

        for plan in [free, basic, premium]:
            for feature_key, enabled in feature_matrix[plan.slug].items():
                feature = FeatureRegistry.objects.filter(key=feature_key).first()
                if not feature:
                    continue
                PlanFeature.objects.update_or_create(
                    plan=plan,
                    feature=feature,
                    defaults={"enabled": enabled},
                )

        now = timezone.now()
        free_invoice, _ = BillingInvoice.objects.get_or_create(
            user=owner,
            payment_reference="DEMO-FREE-START",
            defaults={
                "plan": free,
                "amount": Decimal("0.00"),
                "paid": True,
                "status": "paid",
            },
        )
        basic_invoice, _ = BillingInvoice.objects.get_or_create(
            user=owner,
            payment_reference="DEMO-BASIC-UPGRADE",
            defaults={
                "plan": basic,
                "amount": basic.price_monthly,
                "paid": True,
                "status": "paid",
            },
        )
        premium_invoice, _ = BillingInvoice.objects.get_or_create(
            user=owner,
            payment_reference="DEMO-PREMIUM-UPGRADE",
            defaults={
                "plan": premium,
                "amount": premium.price_monthly,
                "paid": True,
                "status": "paid",
            },
        )

        subscription, _ = Subscription.objects.get_or_create(
            user=owner,
            defaults={
                "plan": premium,
                "invoice": premium_invoice,
                "status": "active",
                "start_date": now - timedelta(days=2),
                "trial_end": now + timedelta(days=premium.trial_days),
            },
        )
        subscription.plan = premium
        subscription.invoice = premium_invoice
        subscription.status = "active"
        subscription.start_date = subscription.start_date or now - timedelta(days=2)
        subscription.trial_end = now + timedelta(days=premium.trial_days)
        subscription.save()

        if not SubscriptionHistory.objects.filter(user=owner, event_type="created", plan=free).exists():
            SubscriptionHistory.objects.create(
                user=owner,
                plan=free,
                event_type="created",
                details={"source": "demo_seed", "invoice": free_invoice.invoice_number},
            )
        if not SubscriptionHistory.objects.filter(user=owner, event_type="upgraded", plan=basic).exists():
            SubscriptionHistory.objects.create(
                user=owner,
                plan=basic,
                event_type="upgraded",
                details={"source": "demo_seed", "invoice": basic_invoice.invoice_number},
            )
        if not SubscriptionHistory.objects.filter(user=owner, event_type="upgraded", plan=premium).exists():
            SubscriptionHistory.objects.create(
                user=owner,
                plan=premium,
                event_type="upgraded",
                details={"source": "demo_seed", "invoice": premium_invoice.invoice_number},
            )

        return {"free": free, "basic": basic, "premium": premium, "subscription": subscription}

    def _set_setting_value(self, *, key: str, value, actor):
        definition = SettingDefinition.objects.filter(key=key).first()
        if not definition:
            return None
        owner = actor if definition.scope == "user" else None
        setting_value, _ = SettingValue.objects.update_or_create(
            definition=definition,
            owner=owner,
            defaults={"value": value, "updated_by": actor},
        )
        return setting_value

    def _seed_branding_and_settings(self, *, owner, plan, admin):
        company, _ = CompanySettings.objects.get_or_create(
            company_name="Demotest3 Retail Private Limited",
            defaults={
                "mobile": "9000000033",
                "email": "hello@demotest3.demo",
            },
        )

        ui = UISettings.objects.first()
        if not ui:
            ui = UISettings.objects.create(
                primary_color="#2b5cff",
                secondary_color="#15b79f",
                success_color="#16a34a",
                danger_color="#dc2626",
                theme_mode="light",
            )
        else:
            ui.primary_color = "#2b5cff"
            ui.secondary_color = "#15b79f"
            ui.theme_mode = "light"
            ui.save(update_fields=["primary_color", "secondary_color", "theme_mode", "updated_at"])

        app = AppSettings.objects.first()
        if not app:
            app = AppSettings.objects.create(
                company_name="Demotest3 Retail Private Limited",
                financial_year_start=timezone.localdate().replace(month=4, day=1),
                currency_symbol="INR",
                maintenance_mode=False,
                enable_notifications=True,
                enable_chat=True,
                allow_user_signup=True,
                allow_social_login=True,
                show_profit_loss=True,
                show_daily_summary=True,
            )
        else:
            app.company_name = "Demotest3 Retail Private Limited"
            app.currency_symbol = "INR"
            app.save(update_fields=["company_name", "currency_symbol", "updated_at"])

        khata_profile, _ = KhataUserProfile.objects.get_or_create(user=owner)
        khata_profile.plan = plan
        khata_profile.full_name = "Demotest 3"
        khata_profile.mobile = "9000000033"
        khata_profile.address = "Shop 14, Civil Lines, Lucknow, Uttar Pradesh"
        khata_profile.business_name = "Demotest3 Retail Private Limited"
        khata_profile.business_type = "Wholesale + Retail"
        khata_profile.gst_number = "09ABCDE1234F1Z5"
        khata_profile.upi_id = "demotest3@upi"
        khata_profile.bank_name = "State Bank of India"
        khata_profile.account_number = "123456789012"
        khata_profile.ifsc_code = "SBIN0001234"
        khata_profile.save()

        account_profile, _ = AccountUserProfile.objects.get_or_create(user=owner, defaults={"full_name": "Demotest 3", "mobile": "9000000033"})
        account_profile.company = company
        account_profile.full_name = "Demotest 3"
        account_profile.mobile = "9000000033"
        account_profile.business_name = "Demotest3 Retail Private Limited"
        account_profile.business_type = "Wholesale + Retail"
        account_profile.gst_number = "09ABCDE1234F1Z5"
        account_profile.address = "Shop 14, Civil Lines, Lucknow, Uttar Pradesh"
        account_profile.plan = plan
        account_profile.save()

        khata_company, _ = KhataCompanySettings.objects.get_or_create(
            company_name="Demotest3 Retail Private Limited",
            defaults={
                "enable_auto_whatsapp": False,
                "enable_monthly_email": True,
            },
        )
        khata_company.whatsapp_number = "919000000033"
        khata_company.whatsapp_api_key = "DEMO-WA-KEY-123"
        khata_company.sms_api_key = "DEMO-SMS-KEY-123"
        khata_company.enable_auto_whatsapp = False
        khata_company.enable_monthly_email = True
        khata_company.save()

        mode = SystemMode.get_solo()
        mode.current_mode = SystemMode.Mode.DESKTOP
        mode.is_locked = False
        mode.updated_by = admin
        mode.save()

        setting_values = {
            "ui_operating_mode": "pc",
            "template_mode_lock": True,
            "quick_scan_mode": "keyboard",
            "auto_print_on_save": True,
            "show_share_actions": True,
            "company_name": "Demotest3 Retail Private Limited",
            "company_logo": "/static/img/logo.png",
            "company_gst": "09ABCDE1234F1Z5",
            "company_address": "Shop 14, Civil Lines, Lucknow, Uttar Pradesh",
            "company_contact": "+91 9000000033",
            "company_bank_details": "SBI A/C 123456789012 IFSC SBIN0001234",
            "company_invoice_footer": "Thank you for your business",
            "company_terms": "Goods once sold will not be taken back without return voucher.",
            "invoice_series": "INV-D3-2026-0001",
            "voucher_numbering": "VCH-D3-YYYY-####",
            "auto_numbering": True,
            "page_size": "Thermal-80mm",
            "thermal_mode": True,
            "print_templates": ["POS Invoice", "A4 Invoice", "Mobile Receipt", "Transport Bill"],
            "qr_code_printing": True,
            "scanner_mapping": {"enter_key_delay": 60, "barcode_type": "auto"},
            "fast_scan": True,
            "auto_add_on_scan": True,
            "whatsapp_api_config": "provider=demo;token=wa-demo-123",
            "order_via_whatsapp": True,
            "invoice_share_auto": True,
            "payment_link_auto": True,
            "sms_gateway_config": "provider=demo-sms",
            "email_smtp_config": "smtp.demo.local:587",
            "website_link": "https://demotest3.jaistech.demo",
            "api_keys_manager": {"public_key": "pk_demo_123", "secret_masked": "****"},
        }
        for key, value in setting_values.items():
            self._set_setting_value(key=key, value=value, actor=owner)

        return {
            "company": company,
            "khata_profile": khata_profile,
            "account_profile": account_profile,
            "ui": ui,
            "app": app,
            "khata_company": khata_company,
        }

    def _seed_products_and_warehouses(self, *, users: DemoUsers):
        unified_warehouse, _ = UnifiedWarehouse.objects.update_or_create(
            code="DARK-LKO-01",
            defaults={
                "name": "Lucknow Dark Store 01",
                "address": "Transport Nagar, Lucknow",
                "latitude": Decimal("26.846695"),
                "longitude": Decimal("80.946166"),
                "capacity_units": 15000,
                "is_dark_store": True,
                "is_active": True,
            },
        )
        WarehouseStaffAssignment.objects.update_or_create(
            warehouse=unified_warehouse,
            user=users.vendor,
            defaults={"is_primary": True},
        )
        WarehouseStaffAssignment.objects.update_or_create(
            warehouse=unified_warehouse,
            user=users.staff,
            defaults={"is_primary": False},
        )

        commerce_warehouse, _ = CommerceWarehouse.objects.get_or_create(
            name="Lucknow Main Warehouse",
            defaults={
                "location": "Transport Nagar, Lucknow",
                "capacity": 12000,
            },
        )
        commerce_warehouse.location = "Transport Nagar, Lucknow"
        commerce_warehouse.capacity = 12000
        commerce_warehouse.save(update_fields=["location", "capacity", "created_at"])

        staples_category, _ = UnifiedCategory.objects.update_or_create(
            slug="staples-demo",
            defaults={"name": "Staples", "is_active": True},
        )
        beverages_category, _ = UnifiedCategory.objects.update_or_create(
            slug="beverages-demo",
            defaults={"name": "Beverages", "is_active": True},
        )

        unified_products_data = [
            {
                "name": "Basmati Rice 25KG",
                "category": staples_category,
                "sku": "DEMO-RICE-25",
                "barcode": "8901001001001",
                "gst_percent": Decimal("5.00"),
                "mrp": Decimal("2100.00"),
                "b2b_price": Decimal("1870.00"),
                "b2c_price": Decimal("1990.00"),
                "wholesale_price": Decimal("1760.00"),
                "fast_moving": True,
                "low_stock_threshold": 12,
            },
            {
                "name": "Chana Dal 30KG",
                "category": staples_category,
                "sku": "DEMO-CHANA-30",
                "barcode": "8901001001002",
                "gst_percent": Decimal("5.00"),
                "mrp": Decimal("2400.00"),
                "b2b_price": Decimal("2130.00"),
                "b2c_price": Decimal("2290.00"),
                "wholesale_price": Decimal("2040.00"),
                "fast_moving": True,
                "low_stock_threshold": 10,
            },
            {
                "name": "Refined Oil 1L",
                "category": staples_category,
                "sku": "DEMO-OIL-1L",
                "barcode": "8901001001003",
                "gst_percent": Decimal("5.00"),
                "mrp": Decimal("170.00"),
                "b2b_price": Decimal("145.00"),
                "b2c_price": Decimal("158.00"),
                "wholesale_price": Decimal("138.00"),
                "fast_moving": True,
                "low_stock_threshold": 50,
            },
            {
                "name": "Kaju Premium 1KG",
                "category": staples_category,
                "sku": "DEMO-KAJU-1KG",
                "barcode": "8901001001004",
                "gst_percent": Decimal("12.00"),
                "mrp": Decimal("1150.00"),
                "b2b_price": Decimal("980.00"),
                "b2c_price": Decimal("1045.00"),
                "wholesale_price": Decimal("930.00"),
                "fast_moving": False,
                "low_stock_threshold": 8,
            },
            {
                "name": "Masala Soda 300ML",
                "category": beverages_category,
                "sku": "DEMO-SODA-300",
                "barcode": "8901001001005",
                "gst_percent": Decimal("18.00"),
                "mrp": Decimal("30.00"),
                "b2b_price": Decimal("21.00"),
                "b2c_price": Decimal("26.00"),
                "wholesale_price": Decimal("19.00"),
                "fast_moving": True,
                "low_stock_threshold": 120,
            },
        ]

        unified_products = []
        for row in unified_products_data:
            product, _ = UnifiedProduct.objects.update_or_create(sku=row["sku"], defaults=row)
            unified_products.append(product)
            WarehouseInventory.objects.update_or_create(
                warehouse=unified_warehouse,
                product=product,
                defaults={"available_qty": 400, "reserved_qty": 10},
            )
            ProductPriceRule.objects.update_or_create(
                product=product,
                channel="quick",
                min_qty=1,
                defaults={"max_qty": None, "override_price": product.b2c_price, "is_active": True},
            )

        commerce_category, _ = CommerceCategory.objects.get_or_create(
            owner=users.owner,
            name="Retail Items",
            defaults={"description": "Retail sale products"},
        )
        commerce_category.description = "Retail sale products"
        commerce_category.save(update_fields=["description"])

        commerce_products_data = [
            ("CMR-DEMO-001", "Aachal Ji Chenna Powder 1KG", Decimal("7000.00"), 18),
            ("CMR-DEMO-002", "Kaju W240 1KG", Decimal("980.00"), 12),
            ("CMR-DEMO-003", "Bori Packing 1pc", Decimal("35.00"), 18),
            ("CMR-DEMO-004", "Sugar 50KG", Decimal("2450.00"), 5),
        ]
        commerce_products = []
        for sku, name, price, gst_rate in commerce_products_data:
            product, _ = CommerceProduct.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": commerce_category,
                    "price": price,
                    "stock": 240,
                    "description": f"Demo product: {name}",
                    "unit": "Nos",
                    "gst_rate": Decimal(str(gst_rate)),
                    "owner": users.owner,
                },
            )
            commerce_products.append(product)

        CommissionRule.objects.update_or_create(
            name="Demo Margin Rule",
            defaults={
                "salesman_percent": Decimal("8.50"),
                "delivery_percent": Decimal("4.50"),
                "is_default": True,
                "is_active": True,
            },
        )

        return {
            "unified_warehouse": unified_warehouse,
            "commerce_warehouse": commerce_warehouse,
            "unified_products": unified_products,
            "commerce_products": commerce_products,
        }

    def _seed_parties_and_transactions(self, *, users: DemoUsers, stock_payload):
        party_data = [
            {
                "name": "Anita Retail",
                "party_type": "customer",
                "mobile": "9123456710",
                "email": "anita.retail@example.com",
                "upi_id": "anita.retail@upi",
                "bank_account_number": "222233334444",
                "whatsapp_number": "919123456710",
                "sms_number": "919123456710",
                "is_premium": True,
                "customer_category": "A",
            },
            {
                "name": "Bharat Traders",
                "party_type": "customer",
                "mobile": "9123456711",
                "email": "bharat.traders@example.com",
                "upi_id": "bharat.traders@upi",
                "bank_account_number": "222233334445",
                "whatsapp_number": "919123456711",
                "sms_number": "919123456711",
                "is_premium": False,
                "customer_category": "B",
            },
            {
                "name": "City Mart",
                "party_type": "customer",
                "mobile": "9123456712",
                "email": "citymart@example.com",
                "upi_id": "citymart@upi",
                "bank_account_number": "222233334446",
                "whatsapp_number": "919123456712",
                "sms_number": "919123456712",
                "is_premium": True,
                "customer_category": "A",
            },
            {
                "name": "Fresh Farm Supply",
                "party_type": "supplier",
                "mobile": "9123456713",
                "email": "freshfarm@example.com",
                "upi_id": "freshfarm@upi",
                "bank_account_number": "333344445551",
                "whatsapp_number": "919123456713",
                "sms_number": "919123456713",
                "is_premium": True,
                "customer_category": "Supplier",
            },
            {
                "name": "Metro Wholesale",
                "party_type": "supplier",
                "mobile": "9123456714",
                "email": "metro.wholesale@example.com",
                "upi_id": "metro.wholesale@upi",
                "bank_account_number": "333344445552",
                "whatsapp_number": "919123456714",
                "sms_number": "919123456714",
                "is_premium": False,
                "customer_category": "Supplier",
            },
        ]

        parties = []
        post_save.disconnect(auto_create_login_link, sender=Party)
        try:
            for row in party_data:
                defaults = dict(row)
                defaults["credit_grade"] = "-"
                defaults["credit_period"] = 30
                defaults["opening_balance"] = Decimal("0.00")
                defaults["is_active"] = True
                party, _ = Party.objects.update_or_create(
                    owner=users.owner,
                    name=row["name"],
                    party_type=row["party_type"],
                    defaults=defaults,
                )
                parties.append(party)
        finally:
            post_save.connect(auto_create_login_link, sender=Party)

        today = timezone.localdate()
        tx_data = [
            ("Anita Retail", "credit", "upi", Decimal("7200.00"), today - timedelta(days=31), "Invoice INV-A-0001 settled"),
            ("Anita Retail", "debit", "cash", Decimal("9800.00"), today - timedelta(days=29), "Sales bill SB-3111"),
            ("Bharat Traders", "debit", "cash", Decimal("12800.00"), today - timedelta(days=22), "Bulk sale with 5% discount"),
            ("Bharat Traders", "credit", "bank", Decimal("5000.00"), today - timedelta(days=18), "Partial payment by NEFT"),
            ("City Mart", "debit", "upi", Decimal("8450.00"), today - timedelta(days=15), "POS order settlement"),
            ("City Mart", "credit", "cash", Decimal("2400.00"), today - timedelta(days=13), "Return adjustment"),
            ("Fresh Farm Supply", "debit", "bank", Decimal("21000.00"), today - timedelta(days=10), "Purchase invoice PI-8801"),
            ("Fresh Farm Supply", "credit", "upi", Decimal("11000.00"), today - timedelta(days=7), "Supplier payment UPI"),
            ("Metro Wholesale", "debit", "cheque", Decimal("15600.00"), today - timedelta(days=5), "Stock replenishment"),
            ("Metro Wholesale", "credit", "online", Decimal("7600.00"), today - timedelta(days=2), "Advance settlement"),
        ]
        party_map = {party.name: party for party in parties}
        transactions = []

        for idx, (party_name, txn_type, txn_mode, amount, txn_date, notes) in enumerate(tx_data, start=1):
            party = party_map[party_name]
            tx = KhataTransaction.objects.filter(
                party=party,
                txn_type=txn_type,
                txn_mode=txn_mode,
                amount=amount,
                date=txn_date,
                notes=notes,
            ).first()
            if not tx:
                tx = KhataTransaction(
                    party=party,
                    txn_type=txn_type,
                    txn_mode=txn_mode,
                    amount=amount,
                    date=txn_date,
                    notes=notes,
                    gst_type="gst" if txn_type == "debit" else "nongst",
                )
            if idx <= 4 and not tx.receipt:
                tx.receipt.save(
                    f"demo_receipt_{idx}.png",
                    ContentFile(ONE_BY_ONE_PNG),
                    save=False,
                )
            tx.save()
            transactions.append(tx)

            OfflineMessage.objects.get_or_create(
                party=party,
                channel="whatsapp",
                message=f"[AUTO DEMO] {txn_type.upper()} INR {amount} recorded on {txn_date}",
                defaults={"status": "sent"},
            )

        for party in parties:
            party.credit_grade = compute_credit_grade(party)
            party.save(update_fields=["credit_grade"])

        for party in parties:
            if party.party_type != "customer":
                continue
            ReminderLog.objects.get_or_create(
                party=party,
                reminder_type="due",
                channel="whatsapp",
                scheduled_for=timezone.now() + timedelta(days=2),
                defaults={
                    "status": "sent",
                    "payload": {
                        "template": "due_reminder_v1",
                        "message": f"Dear {party.name}, your outstanding is due soon.",
                    },
                },
            )

        return {"parties": parties, "transactions": transactions}

    def _seed_commerce_documents(self, *, users: DemoUsers, party_payload):
        parties = {p.name: p for p in party_payload["parties"]}
        products = list(CommerceProduct.objects.filter(owner=users.owner).order_by("id"))
        today = timezone.localdate()

        sales_order = CommerceOrder.objects.filter(owner=users.owner, invoice_number="SALE-DEMO-3119").first()
        if not sales_order:
            CommerceOrder.objects.bulk_create(
                [
                    CommerceOrder(
                        owner=users.owner,
                        invoice_number="SALE-DEMO-3119",
                        party=parties["Anita Retail"],
                        placed_by="user",
                        status="accepted",
                        order_type="SALE",
                        notes="Demo smart order entry flow",
                        order_source="POS-PC",
                        assigned_to=users.staff,
                        discount_type="percent",
                        discount_value=Decimal("5.00"),
                        tax_percent=Decimal("18.00"),
                    )
                ]
            )
            sales_order = CommerceOrder.objects.get(owner=users.owner, invoice_number="SALE-DEMO-3119")
        sales_order.party = parties["Anita Retail"]
        sales_order.status = "accepted"
        sales_order.order_type = "SALE"
        sales_order.placed_by = "user"
        sales_order.order_source = "POS-PC"
        sales_order.assigned_to = users.staff
        sales_order.discount_type = "percent"
        sales_order.discount_value = Decimal("5.00")
        sales_order.tax_percent = Decimal("18.00")
        sales_order.notes = "Demo smart order entry flow"
        sales_order.save()

        sales_order.items.all().delete()
        for product, qty in [(products[0], 1), (products[1], 2)]:
            CommerceOrderItem.objects.create(order=sales_order, product=product, qty=qty, price=product.price)
        sales_order.save()
        CommerceOrder.objects.filter(pk=sales_order.pk).update(created_at=timezone.now() - timedelta(days=3))
        sales_order.refresh_from_db()

        invoice, _ = CommerceInvoice.objects.get_or_create(
            order=sales_order,
            defaults={"amount": sales_order.total_amount(), "gst_type": "GST", "status": "unpaid"},
        )
        invoice.amount = sales_order.total_amount()
        invoice.gst_type = "GST"
        invoice.save()

        payment, _ = CommercePayment.objects.get_or_create(
            invoice=invoice,
            reference="UPI-DEMO-3119",
            defaults={
                "amount": invoice.amount,
                "method": "UPI",
                "note": "Demo payment link settlement",
            },
        )
        payment.amount = invoice.amount
        payment.method = "UPI"
        payment.note = "Demo payment link settlement"
        payment.save()
        invoice.status = "paid"
        invoice.save(update_fields=["status"])

        voucher, _ = SalesVoucher.objects.get_or_create(
            order=sales_order,
            party=sales_order.party,
            defaults={"is_gst": True, "total_amount": invoice.amount},
        )
        voucher.is_gst = True
        voucher.total_amount = invoice.amount
        voucher.save()
        voucher.items.all().delete()
        for product, qty in [(products[0], Decimal("1.00")), (products[1], Decimal("2.00"))]:
            SalesVoucherItem.objects.create(
                voucher=voucher,
                product=product,
                qty=qty,
                rate=product.price,
                gst_rate=Decimal("18"),
            )

        purchase_order = CommerceOrder.objects.filter(owner=users.owner, invoice_number="PUR-DEMO-8801").first()
        if not purchase_order:
            CommerceOrder.objects.bulk_create(
                [
                    CommerceOrder(
                        owner=users.owner,
                        invoice_number="PUR-DEMO-8801",
                        party=parties["Fresh Farm Supply"],
                        placed_by="user",
                        status="accepted",
                        order_type="PURCHASE",
                        notes="Monthly stock procurement",
                        order_source="Manual",
                        due_amount=Decimal("0.00"),
                        payment_due_date=today + timedelta(days=10),
                    )
                ]
            )
            purchase_order = CommerceOrder.objects.get(owner=users.owner, invoice_number="PUR-DEMO-8801")
        purchase_order.party = parties["Fresh Farm Supply"]
        purchase_order.status = "accepted"
        purchase_order.order_type = "PURCHASE"
        purchase_order.notes = "Monthly stock procurement"
        purchase_order.payment_due_date = today + timedelta(days=10)
        purchase_order.save()
        purchase_order.items.all().delete()
        for product, qty in [(products[2], 20), (products[3], 8)]:
            CommerceOrderItem.objects.create(order=purchase_order, product=product, qty=qty, price=product.price)
        purchase_order.save()
        purchase_order.due_amount = purchase_order.total_amount() - Decimal("6000.00")
        purchase_order.save(update_fields=["due_amount"])

        SupplierPayment.objects.get_or_create(
            supplier=parties["Fresh Farm Supply"],
            order=purchase_order,
            amount=Decimal("6000.00"),
            payment_mode="bank",
            reference="NEFT-DEMO-8801",
            payment_date=today - timedelta(days=1),
            defaults={"notes": "Partial supplier settlement"},
        )

        return {
            "sales_order": sales_order,
            "invoice": invoice,
            "payment": payment,
            "voucher": voucher,
            "purchase_order": purchase_order,
        }

    def _create_or_update_unified_order(
        self,
        *,
        order_number: str,
        customer,
        salesman,
        warehouse,
        product_rows,
        created_at,
        status: str,
    ):
        order, _ = UnifiedOrder.objects.get_or_create(
            order_number=order_number,
            defaults={
                "order_type": UnifiedOrder.OrderType.ONLINE,
                "customer": customer,
                "salesman": salesman,
                "warehouse": warehouse,
                "status": status,
                "notes": "AI demo order",
            },
        )
        order.order_type = UnifiedOrder.OrderType.ONLINE
        order.customer = customer
        order.salesman = salesman
        order.warehouse = warehouse
        order.status = status
        order.notes = "AI demo order"
        order.save()

        order.items.all().delete()
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")
        cost_amount = Decimal("0.00")
        margin_amount = Decimal("0.00")

        for product, qty in product_rows:
            unit_price = product.b2c_price
            unit_cost = product.wholesale_price
            base = unit_price * qty
            tax = base * (product.gst_percent / Decimal("100.00"))
            line_total = base + tax
            margin = (unit_price - unit_cost) * qty
            UnifiedOrderItem.objects.create(
                order=order,
                product=product,
                qty=qty,
                unit_price=unit_price,
                unit_cost=unit_cost,
                tax_percent=product.gst_percent,
                line_discount=Decimal("0.00"),
                line_total=line_total,
                margin_total=margin,
            )
            subtotal += base
            tax_amount += tax
            cost_amount += unit_cost * qty
            margin_amount += margin

        order.subtotal = subtotal
        order.tax_amount = tax_amount
        order.discount_amount = Decimal("0.00")
        order.total_amount = subtotal + tax_amount
        order.cost_amount = cost_amount
        order.margin_amount = margin_amount
        order.save(
            update_fields=[
                "subtotal",
                "tax_amount",
                "discount_amount",
                "total_amount",
                "cost_amount",
                "margin_amount",
                "updated_at",
            ]
        )

        UnifiedOrder.objects.filter(pk=order.pk).update(created_at=created_at, updated_at=created_at + timedelta(minutes=5))
        order.refresh_from_db()
        return order

    def _seed_unified_orders_and_ai(self, *, users: DemoUsers, stock_payload):
        warehouse = stock_payload["unified_warehouse"]
        products = stock_payload["unified_products"]
        today = timezone.now()

        low_risk_schedule = [
            ("DEMO-LOW-001", users.risk_low, UnifiedOrder.Status.DELIVERED, [(products[0], 1), (products[2], 3)], 160),
            ("DEMO-LOW-002", users.risk_low, UnifiedOrder.Status.DELIVERED, [(products[1], 1), (products[2], 2)], 140),
            ("DEMO-LOW-003", users.risk_low, UnifiedOrder.Status.PACKED, [(products[2], 4)], 90),
        ]
        medium_risk_schedule = [
            ("DEMO-MED-001", users.risk_medium, UnifiedOrder.Status.DELIVERED, [(products[0], 1)], 130),
            ("DEMO-MED-002", users.risk_medium, UnifiedOrder.Status.CANCELLED, [(products[3], 1)], 110),
            ("DEMO-MED-003", users.risk_medium, UnifiedOrder.Status.OUT_FOR_DELIVERY, [(products[2], 3)], 70),
        ]
        high_risk_schedule = [
            ("DEMO-HIGH-001", users.risk_high, UnifiedOrder.Status.DELIVERED, [(products[3], 2)], 120),
            ("DEMO-HIGH-002", users.risk_high, UnifiedOrder.Status.CANCELLED, [(products[0], 1)], 95),
            ("DEMO-HIGH-003", users.risk_high, UnifiedOrder.Status.DELIVERED, [(products[1], 1)], 55),
        ]
        timeline = low_risk_schedule + medium_risk_schedule + high_risk_schedule

        orders = []
        for order_no, customer, status, items, days_ago in timeline:
            created_at = today - timedelta(days=days_ago)
            order = self._create_or_update_unified_order(
                order_number=order_no,
                customer=customer,
                salesman=users.salesman,
                warehouse=warehouse,
                product_rows=items,
                created_at=created_at,
                status=status,
            )
            orders.append(order)

            payment_status = PaymentTransaction.Status.SUCCESS
            if "HIGH" in order_no and order_no.endswith("002"):
                payment_status = PaymentTransaction.Status.FAILED
            if "MED" in order_no and order_no.endswith("002"):
                payment_status = PaymentTransaction.Status.FAILED

            pay, _ = PaymentTransaction.objects.get_or_create(
                external_ref=f"PAY-{order_no}",
                defaults={
                    "order": order,
                    "user": customer,
                    "mode": PaymentTransaction.Mode.UPI,
                    "status": payment_status,
                    "amount": order.total_amount,
                },
            )
            pay.order = order
            pay.user = customer
            pay.mode = PaymentTransaction.Mode.UPI
            pay.status = payment_status
            pay.amount = order.total_amount
            pay.save()
            PaymentTransaction.objects.filter(pk=pay.pk).update(created_at=created_at + timedelta(days=2))

            if not CommissionPayout.objects.filter(order=order).exists():
                rule = CommissionRule.objects.filter(is_default=True).first()
                if not rule:
                    rule = CommissionRule.objects.create(
                        name="Auto Demo Rule",
                        salesman_percent=Decimal("8.50"),
                        delivery_percent=Decimal("4.50"),
                        is_default=True,
                        is_active=True,
                    )
                CommissionPayout.objects.create(
                    order=order,
                    rule=rule,
                    margin_amount=order.margin_amount,
                    salesman_amount=(order.margin_amount * rule.salesman_percent) / Decimal("100.00"),
                    delivery_amount=(order.margin_amount * rule.delivery_percent) / Decimal("100.00"),
                    company_profit=order.margin_amount
                    - ((order.margin_amount * rule.salesman_percent) / Decimal("100.00"))
                    - ((order.margin_amount * rule.delivery_percent) / Decimal("100.00")),
                )

            assignment, _ = DeliveryAssignment.objects.get_or_create(
                order=order,
                defaults={
                    "partner": users.delivery,
                    "otp_code": "123456",
                    "status": DeliveryAssignment.Status.DELIVERED if status == UnifiedOrder.Status.DELIVERED else DeliveryAssignment.Status.ASSIGNED,
                    "estimated_distance_km": Decimal("8.50"),
                    "payout_amount": Decimal("42.50"),
                    "tracking_payload": {"route": "demo-route"},
                },
            )
            assignment.partner = users.delivery
            assignment.status = DeliveryAssignment.Status.DELIVERED if status == UnifiedOrder.Status.DELIVERED else DeliveryAssignment.Status.ASSIGNED
            assignment.tracking_payload = {"route": "demo-route"}
            assignment.save()
            if not assignment.pings.exists():
                DeliveryTrackingPing.objects.create(
                    assignment=assignment,
                    latitude=Decimal("26.846700"),
                    longitude=Decimal("80.946200"),
                    speed_kmph=Decimal("24.00"),
                )

        pos_order = self._create_or_update_unified_order(
            order_number="POS-DEMO-0001",
            customer=users.customer,
            salesman=users.salesman,
            warehouse=warehouse,
            product_rows=[(products[2], 5)],
            created_at=today - timedelta(days=1),
            status=UnifiedOrder.Status.DELIVERED,
        )
        pos_order.order_type = UnifiedOrder.OrderType.POS
        pos_order.walk_in_customer_name = "Walk-in Customer Demo"
        pos_order.save(update_fields=["order_type", "walk_in_customer_name", "updated_at"])

        POSBill.objects.update_or_create(
            order=pos_order,
            defaults={
                "bill_number": "POS-2026-0001",
                "cashier": users.staff,
                "terminal_id": "POS-PC-01",
                "payment_mode": "cash",
                "printed_at": timezone.now(),
            },
        )
        PaymentTransaction.objects.update_or_create(
            external_ref="PAY-POS-DEMO-0001",
            defaults={
                "order": pos_order,
                "user": users.customer,
                "mode": PaymentTransaction.Mode.CASH,
                "status": PaymentTransaction.Status.SUCCESS,
                "amount": pos_order.total_amount,
            },
        )
        DailyCashSummary.objects.update_or_create(
            cashier=users.staff,
            business_date=timezone.localdate(),
            defaults={
                "opening_cash": Decimal("2500.00"),
                "cash_in": Decimal("6200.00"),
                "cash_out": Decimal("900.00"),
                "closing_cash": Decimal("7800.00"),
            },
        )

        ai_result = run_all_ai_engines()
        return {
            "orders": orders,
            "pos_order": pos_order,
            "ai_result": ai_result,
            "risk_scores": list(CustomerRiskScore.objects.select_related("customer").all()),
            "salesman_scores": list(SalesmanScore.objects.select_related("salesman").all()),
            "forecasts": list(ProductDemandForecast.objects.select_related("product").all()[:20]),
        }

    def _seed_print_and_scanner(self, *, users: DemoUsers, commerce_payload):
        printer, _ = PrinterConfig.objects.update_or_create(
            user=users.owner,
            model_name="EPSON-TM-T82X-DEMO",
            defaults={
                "printer_type": PrinterConfig.PrinterType.THERMAL_80,
                "connection_type": PrinterConfig.ConnectionType.USB,
                "auto_print": True,
                "include_logo": True,
                "include_qr": True,
                "include_barcode": True,
                "template_html": "",
                "connection_payload": {"usb_port": "USB001"},
                "is_default": True,
            },
        )
        scanner, _ = ScannerConfig.objects.update_or_create(
            user=users.owner,
            model_name="Zebra DS2208 Demo",
            defaults={
                "scanner_type": ScannerConfig.ScannerType.USB_HID,
                "barcode_types_supported": ["EAN13", "CODE128", "QR"],
                "scanning_delay_ms": 80,
                "auto_submit": True,
                "sound_enabled": True,
                "default_action_after_scan": "add_item",
                "camera_constraints": {"facingMode": "environment"},
                "is_default": True,
            },
        )
        for code in ["8901001001001", "8901001001002", "8901001001004"]:
            ScanEvent.objects.get_or_create(
                user=users.owner,
                scanner_config=scanner,
                raw_code=code,
                defaults={"code_type": "ean13", "metadata": {"source": "demo_seed"}},
            )

        base_templates = {
            PrintDocumentType.INVOICE: PrintTemplate.objects.filter(document_type=PrintDocumentType.INVOICE).first(),
            PrintDocumentType.RECEIPT: PrintTemplate.objects.filter(document_type=PrintDocumentType.RECEIPT).first(),
            PrintDocumentType.TRANSPORT_RECEIPT: PrintTemplate.objects.filter(document_type=PrintDocumentType.TRANSPORT_RECEIPT).first(),
        }

        user_templates = []
        template_specs = [
            ("POS Invoice Template", PrintDocumentType.INVOICE, PrintMode.POS, PrintPaperSize.POS_80, True),
            ("A4 Invoice Template", PrintDocumentType.INVOICE, PrintMode.DESKTOP, PrintPaperSize.A4, False),
            ("Mobile Receipt Template", PrintDocumentType.RECEIPT, PrintMode.MOBILE, PrintPaperSize.MOBILE, False),
            ("Transport Bill Template", PrintDocumentType.TRANSPORT_RECEIPT, PrintMode.TABLET, PrintPaperSize.TABLET, False),
        ]
        for name, doc_type, mode, paper_size, thermal in template_specs:
            user_template, _ = UserPrintTemplate.objects.update_or_create(
                user=users.owner,
                name=name,
                defaults={
                    "template": base_templates.get(doc_type),
                    "document_type": doc_type,
                    "print_mode": mode,
                    "is_active": True,
                    "is_default": True,
                    "theme_mode": "light",
                    "company_name": "Demotest3 Retail Private Limited",
                    "company_address": "Shop 14, Civil Lines, Lucknow",
                    "company_phone": "+91 9000000033",
                    "company_email": "hello@demotest3.demo",
                    "company_tax_id": "09ABCDE1234F1Z5",
                    "header_text": name,
                    "footer_text": "Thank you for your business",
                    "primary_color": "#2b5cff",
                    "secondary_color": "#0f172a",
                    "accent_color": "#e2e8f0",
                    "font_family": "Arial, sans-serif",
                    "font_size": 12,
                    "paper_size": paper_size,
                    "thermal_mode": thermal,
                    "auto_print": True,
                    "qr_enabled": True,
                    "barcode_enabled": True,
                    "show_digital_signature": False,
                    "show_stamp": False,
                },
            )
            UserPrintTemplate.objects.filter(
                user=users.owner,
                document_type=doc_type,
                print_mode=mode,
            ).exclude(pk=user_template.pk).update(is_default=False)
            user_templates.append(user_template)

        render_logs = []
        for user_template in user_templates:
            context = build_dummy_context(document_type=user_template.document_type, user=users.owner)
            rendered = render_template_payload(
                document_type=user_template.document_type,
                context=context,
                template_obj=user_template.template,
                user_template=user_template,
                print_mode=user_template.print_mode,
            )
            log, _ = PrintRenderLog.objects.update_or_create(
                user=users.owner,
                user_template=user_template,
                source_model="demo_seed",
                source_id=str(commerce_payload["invoice"].id),
                defaults={
                    "template": user_template.template,
                    "document_type": user_template.document_type,
                    "print_mode": user_template.print_mode,
                    "paper_size": rendered["config"].get("paper_size", user_template.paper_size),
                    "status": PrintRenderLog.Status.SUCCESS,
                    "payload": {"sample": True},
                    "rendered_html": rendered["html"][:15000],
                    "rendered_css": rendered["css"][:5000],
                },
            )
            render_logs.append(log)

        return {
            "printer": printer,
            "scanner": scanner,
            "user_templates": user_templates,
            "render_logs": render_logs,
        }

    def _seed_notifications(self, *, users: DemoUsers, party_payload, commerce_payload):
        for party in party_payload["parties"]:
            OfflineMessage.objects.get_or_create(
                party=party,
                channel="sms",
                message=f"[SMS DEMO] Dear {party.name}, payment reminder generated.",
                defaults={"status": "pending"},
            )
        CommerceNotification.objects.get_or_create(
            message="Demo notification: New online order received.",
            defaults={"is_read": False},
        )
        ReminderLog.objects.get_or_create(
            party=party_payload["parties"][0],
            reminder_type="payment",
            channel="email",
            defaults={
                "status": "sent",
                "payload": {"subject": "Payment reminder demo", "invoice": commerce_payload["invoice"].number},
            },
        )
        return {
            "offline_messages_count": OfflineMessage.objects.count(),
            "reminder_logs_count": ReminderLog.objects.count(),
            "commerce_notifications_count": CommerceNotification.objects.count(),
        }

    def _run_crud_validation(self, *, owner):
        tmp_party = Party.objects.create(
            owner=owner,
            name="ZZZ CRUD TEMP",
            mobile="",
            email="",
            party_type="customer",
            is_premium=False,
        )
        created_ok = Party.objects.filter(pk=tmp_party.pk).exists()
        tmp_party.name = "ZZZ CRUD TEMP UPDATED"
        tmp_party.save(update_fields=["name"])
        updated_ok = Party.objects.filter(pk=tmp_party.pk, name="ZZZ CRUD TEMP UPDATED").exists()
        tmp_party_id = tmp_party.pk
        tmp_party.delete()
        deleted_ok = not Party.objects.filter(pk=tmp_party_id).exists()
        return {
            "create": created_ok,
            "update": updated_ok,
            "delete": deleted_ok,
            "all_passed": created_ok and updated_ok and deleted_ok,
        }

    def _build_payment_links(self, *, party_payload, commerce_payload, profile):
        upi_link = commerce_payload["invoice"].payment_link or ""
        qr_link = f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={quote_plus(upi_link)}" if upi_link else ""
        bank_link = (
            f"https://payments.jaistech.demo/bank-transfer?bank={quote_plus(profile.bank_name or '')}"
            f"&acc={quote_plus(profile.account_number or '')}&ifsc={quote_plus(profile.ifsc_code or '')}"
        )
        party_links = {party.name: party.get_payment_link() for party in party_payload["parties"]}
        return {
            "upi_link": upi_link,
            "qr_link": qr_link,
            "bank_link": bank_link,
            "party_links": party_links,
        }

    def _build_dataset(
        self,
        *,
        users,
        plans,
        settings_payload,
        party_payload,
        commerce_payload,
        ai_payload,
        print_payload,
        payment_links,
        notification_payload,
        crud_payload,
        output_dir: Path,
    ):
        parties = party_payload["parties"]
        txns = party_payload["transactions"]
        party_rows = []
        for party in parties:
            party_rows.append(
                {
                    "name": party.name,
                    "type": party.party_type,
                    "mobile": party.mobile,
                    "upi_id": party.upi_id,
                    "bank_account": party.bank_account_number,
                    "whatsapp": party.whatsapp_number,
                    "sms": party.sms_number,
                    "premium": party.is_premium,
                    "credit_grade": party.credit_grade,
                    "total_credit": str(party.total_credit()),
                    "total_debit": str(party.total_debit()),
                    "balance": str(party.balance()),
                }
            )

        tx_rows = []
        for tx in sorted(txns, key=lambda x: x.date):
            tx_rows.append(
                {
                    "id": tx.id,
                    "party": tx.party.name,
                    "type": tx.txn_type,
                    "mode": tx.txn_mode,
                    "amount": str(tx.amount),
                    "date": str(tx.date),
                    "notes": tx.notes,
                    "has_receipt": bool(tx.receipt),
                }
            )

        risk_rows = [
            {
                "customer": row.customer.email,
                "score": row.risk_score,
                "level": row.risk_level,
                "last_calculated": row.last_calculated.isoformat(),
            }
            for row in ai_payload["risk_scores"]
        ]
        salesman_rows = [
            {
                "salesman": row.salesman.email,
                "performance_score": row.performance_score,
                "risk_flag": row.risk_flag,
                "calculated_at": row.calculated_at.isoformat(),
            }
            for row in ai_payload["salesman_scores"]
        ]

        checklist = [
            ("User Signup/Login (Demotest3)", bool(users.owner and users.owner.is_active)),
            ("Role-based access users", UserProfileExt.objects.count() >= 8),
            ("Branding setup", bool(settings_payload["khata_profile"].business_name and settings_payload["khata_profile"].gst_number)),
            ("Admin panel demo data", bool(users.admin.is_superuser)),
            ("Plan management (Free/Basic/Premium)", Plan.objects.filter(slug__in=["free-plan", "basic-plan", "premium-plan"]).count() == 3),
            ("Feature toggles", FeatureRegistry.objects.filter(key__in=["communication.whatsapp", "reports.pdf_export", "payments.link", "credit.report", "template.editor"]).count() == 5),
            ("Party creation (5)", len(parties) == 5),
            ("Transactions (>=10)", len(txns) >= 10),
            ("Payment links (UPI/QR/Bank)", bool(payment_links["upi_link"] and payment_links["qr_link"] and payment_links["bank_link"])),
            ("Invoice/Receipt/Bill generation", bool(commerce_payload["invoice"] and commerce_payload["voucher"])),
            ("Template selection (POS/A4/Mobile/Tablet)", len(print_payload["user_templates"]) >= 4),
            ("Credit score calculation", len(risk_rows) >= 3),
            ("Monthly reporting data", KhataTransaction.objects.count() >= 10),
            ("Due reminder automation logs", ReminderLog.objects.filter(reminder_type="due").count() >= 1),
            ("User dashboard data", Party.objects.filter(owner=users.owner).count() >= 5),
            ("Multi-device print preview logs", len(print_payload["render_logs"]) >= 4),
            ("White-label domain", Site.objects.get_current().domain == "demotest3.jaistech.demo"),
            ("Backup file presence", Path("db_backup.sqlite3").exists()),
            ("API demo data ready", len(ai_payload["forecasts"]) > 0),
            ("Notification system logs", notification_payload["offline_messages_count"] > 0),
            ("Stock/items available", UnifiedProduct.objects.count() > 0 and CommerceProduct.objects.count() > 0),
            ("Settings center values", SettingValue.objects.count() > 0),
            ("CRUD validation", crud_payload["all_passed"]),
        ]

        totals = {
            "parties": len(parties),
            "transactions": len(txns),
            "total_credit": str(sum((tx.amount for tx in txns if tx.txn_type == "credit"), Decimal("0.00"))),
            "total_debit": str(sum((tx.amount for tx in txns if tx.txn_type == "debit"), Decimal("0.00"))),
            "net_balance": str(
                sum((tx.amount for tx in txns if tx.txn_type == "debit"), Decimal("0.00"))
                - sum((tx.amount for tx in txns if tx.txn_type == "credit"), Decimal("0.00"))
            ),
        }

        return {
            "generated_at": timezone.now().isoformat(),
            "credentials": {
                "username": users.owner.username,
                "email": users.owner.email,
                "password": "Demo@123",
                "admin_email": users.admin.email,
            },
            "business_profile": {
                "business_name": settings_payload["khata_profile"].business_name,
                "address": settings_payload["khata_profile"].address,
                "gst_no": settings_payload["khata_profile"].gst_number,
                "upi_id": settings_payload["khata_profile"].upi_id,
                "theme_primary": settings_payload["ui"].primary_color,
                "pos_print_mode": "Thermal-80mm",
                "invoice_preferences": "Auto numbering + QR + barcode + share actions",
                "custom_domain": Site.objects.get_current().domain,
            },
            "plans": {
                "free": {"name": plans["free"].name, "monthly": str(plans["free"].price_monthly)},
                "basic": {"name": plans["basic"].name, "monthly": str(plans["basic"].price_monthly)},
                "premium": {"name": plans["premium"].name, "monthly": str(plans["premium"].price_monthly)},
                "active_plan": plans["subscription"].plan.name,
            },
            "parties": party_rows,
            "transactions": tx_rows,
            "payment_links": payment_links,
            "ai": {
                "run_result": ai_payload["ai_result"],
                "risk_scores": risk_rows,
                "salesman_scores": salesman_rows,
                "forecast_rows": len(ai_payload["forecasts"]),
            },
            "documents": {
                "sales_order_id": commerce_payload["sales_order"].id,
                "invoice_number": commerce_payload["invoice"].number,
                "voucher_number": commerce_payload["voucher"].invoice_no,
                "purchase_order_id": commerce_payload["purchase_order"].id,
            },
            "templates": [
                {
                    "name": t.name,
                    "document_type": t.document_type,
                    "print_mode": t.print_mode,
                    "paper_size": t.paper_size,
                }
                for t in print_payload["user_templates"]
            ],
            "totals": totals,
            "module_checklist": [{"module": name, "status": "PASS" if status else "FAIL"} for name, status in checklist],
            "paths": {
                "json": str(output_dir / "demotest3_demo_dataset.json"),
                "markdown": str(output_dir / "DEMOTEST3_E2E_DEMO_FLOW.md"),
                "credit_report_all_pdf": str(output_dir / "credit_report_all_demotest3.pdf"),
                "credit_report_sample_pdf": str(output_dir / "credit_report_anita_retail.pdf"),
            },
        }

    def _write_credit_reports(self, *, output_dir: Path, parties):
        output_dir.mkdir(parents=True, exist_ok=True)
        all_pdf = generate_credit_report_pdf()
        (output_dir / "credit_report_all_demotest3.pdf").write_bytes(all_pdf.read())
        sample_party = next((p for p in parties if p.name == "Anita Retail"), parties[0] if parties else None)
        if sample_party:
            party_pdf = generate_credit_report_pdf_for_party(sample_party)
            (output_dir / "credit_report_anita_retail.pdf").write_bytes(party_pdf.read())

    def _write_dataset_json(self, *, dataset: dict, output_dir: Path):
        json_path = output_dir / "demotest3_demo_dataset.json"
        json_path.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    def _write_demo_markdown(self, *, dataset: dict, output_dir: Path):
        checklist_rows = "\n".join(
            f"| {row['module']} | {row['status']} |"
            for row in dataset["module_checklist"]
        )
        party_rows = "\n".join(
            f"| {idx} | {p['name']} | {p['type']} | {p['mobile']} | {p['upi_id']} | {p['credit_grade']} |"
            for idx, p in enumerate(dataset["parties"], start=1)
        )
        tx_rows = "\n".join(
            f"| {idx} | {t['date']} | {t['party']} | {t['type']} | {t['mode']} | INR {t['amount']} | {t['notes']} |"
            for idx, t in enumerate(dataset["transactions"], start=1)
        )

        markdown = f"""# Demotest3 End-to-End Demo Flow

## 1. Demo Credentials
- Demo User: `{dataset['credentials']['username']}` (`{dataset['credentials']['email']}`)
- Demo Password: `{dataset['credentials']['password']}`
- Admin User: `{dataset['credentials']['admin_email']}`
- Active Plan: `{dataset['plans']['active_plan']}`

## 2. Demo Dataset
### Business Profile
- Business Name: {dataset['business_profile']['business_name']}
- Address: {dataset['business_profile']['address']}
- GST: {dataset['business_profile']['gst_no']}
- UPI: {dataset['business_profile']['upi_id']}
- Theme Primary: {dataset['business_profile']['theme_primary']}
- POS Print Mode: {dataset['business_profile']['pos_print_mode']}
- Custom Domain (White-label): {dataset['business_profile']['custom_domain']}

### Parties (3 Customers + 2 Suppliers)
| # | Name | Type | Mobile | UPI | Credit Grade |
|---|---|---|---|---|---|
{party_rows}

### Transactions (10 Mixed Credit/Debit)
| # | Date | Party | Type | Mode | Amount | Notes |
|---|---|---|---|---|---|---|
{tx_rows}

### Payment Links
- UPI Link: `{dataset['payment_links']['upi_link']}`
- QR Link: `{dataset['payment_links']['qr_link']}`
- Bank Link: `{dataset['payment_links']['bank_link']}`

### Templates Assigned
{chr(10).join([f"- {t['name']} ({t['document_type']} / {t['print_mode']} / {t['paper_size']})" for t in dataset['templates']])}

## 3. Demo Storyline (Step-by-Step)
1. Admin opens `/superadmin/`, creates/updates Free, Basic, Premium plans and feature matrix.
2. User logs in as `Demotest3` and opens dashboard `/accounts/dashboard/`.
3. User configures branding in settings center `/settings/center/`.
4. User enables WhatsApp/SMS/Email configs in settings center.
5. User creates/opens party list at `/app/party/list/` with 5 demo parties.
6. User enters transactions at `/app/transaction/add/` and views list at `/app/transactions/`.
7. Auto message logs are visible in `OfflineMessage` + `ReminderLog`.
8. User creates sales order at `/commerce/add-order/`.
9. User generates invoice/payment at `/commerce/add-invoice/` and `/commerce/add-payment/`.
10. User views print templates via `/api/printers/user-templates/`.
11. User tests POS print flow and A4 flow using render endpoint `/api/printers/engine/render/`.
12. User checks AI scores via `/api/ai/credit-risk/`, `/api/ai/forecast/`, `/api/ai/salesman-score/`.
13. User downloads credit report PDF from generated files.
14. User verifies due reminders and notifications.
15. User upgrades plan flow is visible from billing history + subscription events.
16. Admin verifies activity from admin list and logs.
17. User exports/uses JSON demo dataset `demotest3_demo_dataset.json`.
18. User validates settings pages and module toggles.
19. User verifies totals and formulas below.
20. Final PASS/FAIL checklist confirms full system demo readiness.

## 4. Mocked Screenshot Script
1. Login page showing Demotest3 credentials entered.
2. Dashboard cards: total parties, total debit, total credit, net position.
3. Party list showing 5 parties and credit grades.
4. Add transaction form with receipt upload.
5. Order entry screen with item rows and shortcuts.
6. Invoice preview with QR + barcode.
7. Payment link popup showing UPI/QR/Bank options.
8. POS print preview (80mm thermal).
9. A4 print preview (desktop invoice).
10. AI panel showing risk score + forecast rows.
11. Billing history page with upgrade timeline (Free -> Basic -> Premium).
12. Admin module checklist with PASS status.

## 5. Calculation Formulas Used
- Party Balance = `Total Credit - Total Debit`
- Net Ledger Position = `Sum(Debit) - Sum(Credit)`
- Order Total = `Subtotal - Discount + Tax`
- Margin = `Total Amount - Cost Amount`
- Credit Grade:
  - `ratio = (debit / credit) * 100`
  - `A+ >= 90`, `A >= 70`, `B >= 50`, `C >= 30`, else `D`
- Risk Score = weighted penalties from unpaid coverage + overdue + failed payments + collection delay
- Salesman Score = `sales component + quality component + collection component`

## 6. Expected Module Output
- Billing: invoice number, payment reference, active subscription.
- Party/Transaction: updated balances, receipt tag, reminder logs.
- Commerce: order items, invoice, sales voucher, supplier due tracking.
- POS/Print: render logs for POS, A4, mobile, tablet.
- AI: forecast rows + customer risk + salesman performance.
- Notifications: WhatsApp/SMS/Email reminder logs.
- Settings: operating mode, print mode, branding and communication config.

## 7. What Client Will See
- Single unified platform with accounting + commerce + POS + AI.
- One user (`Demotest3`) running realistic daily workflow.
- Admin control over plans, features, mode, and monitoring.
- Ready-to-show demo assets: data JSON + markdown playbook + credit report PDFs.

## 8. Totals Verification
- Total Parties: **{dataset['totals']['parties']}**
- Total Transactions: **{dataset['totals']['transactions']}**
- Total Credit: **INR {dataset['totals']['total_credit']}**
- Total Debit: **INR {dataset['totals']['total_debit']}**
- Net Balance: **INR {dataset['totals']['net_balance']}**

## 9. PASS/FAIL Checklist
| Module | Status |
|---|---|
{checklist_rows}

## 10. Generated Files
- `{dataset['paths']['json']}`
- `{dataset['paths']['markdown']}`
- `{dataset['paths']['credit_report_all_pdf']}`
- `{dataset['paths']['credit_report_sample_pdf']}`
"""
        md_path = output_dir / "DEMOTEST3_E2E_DEMO_FLOW.md"
        md_path.write_text(markdown, encoding="utf-8")
