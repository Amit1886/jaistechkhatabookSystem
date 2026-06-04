from decimal import Decimal
from random import randint

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from commerce.models import Category, Product as CommerceProduct, Quotation, QuotationItem, StockEntry, Warehouse as CommerceWarehouse
from khataapp.models import CreditAccount, Party, Transaction
from apps.platform.core.models import (
    AutomationRule,
    BackgroundJobDefinition,
    BillOfMaterials,
    ChartOfAccount,
    DashboardDefinition,
    DashboardWidget,
    EventSubscription,
    FeatureToggle,
    FormDefinition,
    FormFieldDefinition,
    GSTLedgerEntry,
    IndustryBlueprint,
    JournalEntry,
    JournalLine,
    MenuItem,
    ModuleDefinition,
    ProcurementRequest,
    Product,
    ProductAttribute,
    ProductVariant,
    ReportDefinition,
    StockLedgerEntry,
    StockTransfer,
    Warehouse,
    WorkflowDefinition,
    WorkflowState,
    WorkflowTransition,
)
from apps.platform.identity.models import (
    AuditLog,
    Branch,
    Company,
    DynamicModule,
    EnterprisePermission,
    EnterpriseRole,
    PermissionOverride,
    RolePermission,
    SmartNotification,
    Tenant,
    TenantMembership,
)
from apps.platform.reporting.models import (
    AnalyticsMetric,
    RealtimeDashboardCounter,
    ReportCategory,
    ReportExport,
    ReportRun,
    ReportTemplate,
    SavedReportFilter,
)
from apps.platform.saas_ecosystem.models import EcosystemPartner, FranchiseAgreement, RoutePlan, SaaSPlan, TenantSubscription, WhiteLabelProfile
from apps.platform.tax_compliance.models import (
    EWayBillRequest,
    GSTInvoice,
    GSTInvoiceLine,
    GSTParty,
    GSTReportSnapshot,
    GSTTaxSlab,
    HSNSACCode,
    PaymentQRProfile,
    TaxAuditLog,
    TaxValidationIssue,
)
from apps.platform.workforce.application.services.execution_service import ToolAssignmentService
from apps.platform.workforce.models import (
    Announcement,
    AttendanceLog,
    BehavioralSignal,
    BusinessNetworkNode,
    CareerGrowthPlan,
    Certification,
    CognitiveEmployeeProfile,
    CultureEngagementProgram,
    Department,
    Designation,
    DisciplineCase,
    EmployeeActivityLog,
    EmployeeDevice,
    EmployeePayrollProfile,
    EmployeeProfile,
    EmployeeRecognition,
    EmployeeScoreSnapshot,
    EmployeeSession,
    EmployeeTransparencyRecord,
    EmployeeWallet,
    ExecutionCommandSnapshot,
    FraudRiskSignal,
    GigTask,
    HRComplianceLedger,
    HRInsight,
    LeaveRequest,
    MarketplaceApplication,
    MarketplaceListing,
    PartnerProfile,
    PartnerSettlement,
    PayrollPolicy,
    PayrollRun,
    PayoutInstruction,
    Payslip,
    ProductivitySignal,
    PublicWorkforceApplication,
    RemoteActivityEvent,
    RemoteWorkSession,
    SelfHealingGovernanceIncident,
    Shift,
    ShiftAssignment,
    StaffDiscussion,
    StaffKPI,
    StaffTask,
    Team,
    TeamChannel,
    TeamMessage,
    TrainingCourse,
    UnifiedDashboardConfig,
    UniversalHardwareDevice,
    WalletTransaction,
    WorkActivityRecord,
    WorkBoard,
    WorkComment,
    WorkItem,
    WorkProject,
    WorkToolDefinition,
    WorkforceProfitabilitySnapshot,
)
from notifications.models import Notification


User = get_user_model()


class Command(BaseCommand):
    help = "Seed a complete enterprise SaaS ERP demo environment for testing."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demotest3@example.com")
        parser.add_argument("--username", default="Demotest3")
        parser.add_argument("--password", default="demotest3")

    @transaction.atomic
    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        username = options["username"].strip()
        password = options["password"]
        today = timezone.localdate()
        now = timezone.now()
        period = today.strftime("%Y-%m")

        demo_user = self._user(
            email=email,
            username=username,
            mobile="9000000003",
            first_name="Demo",
            last_name="Test 3",
            password=password,
            full_access=True,
        )

        tenant, _ = Tenant.objects.update_or_create(
            slug="billentra-enterprise-demo",
            defaults={
                "name": "Billentra Enterprise Demo",
                "status": Tenant.Status.ACTIVE,
                "owner": demo_user,
                "metadata": {"demo": True, "industry_mix": ["grocery", "pharmacy", "restaurant", "garment", "footwear", "distribution"]},
            },
        )
        company, _ = Company.objects.update_or_create(
            tenant=tenant,
            name="Billentra Mega Retail Pvt Ltd",
            defaults={"legal_name": "Billentra Mega Retail Private Limited", "gst_number": "09ABCDE1234F1Z5", "metadata": {"demo": True}},
        )
        branches = self._branches(tenant, company)
        TenantMembership.objects.update_or_create(
            tenant=tenant,
            user=demo_user,
            defaults={"company": company, "branch": branches[0], "is_owner": True, "is_active": True, "metadata": {"role": "super_admin", "full_testing": True}},
        )

        self._grant_full_access(demo_user, tenant)
        departments, designations, teams = self._org(tenant, company, branches)
        staff = self._staff(tenant, company, branches, departments, designations, teams, demo_user, password)
        warehouses, products, variants = self._inventory(tenant, company, branches, today)
        accounts = self._finance(tenant, demo_user)
        invoices = self._tax_flow(tenant, demo_user, today, accounts)
        self._saas_partner_network(tenant, company, branches, staff, today)
        self._workforce_flows(tenant, company, branches, departments, staff, demo_user, period, today, now)
        self._execution_cloud(tenant, departments, staff, demo_user, period, today, now)
        self._platform_metadata(tenant, demo_user)
        self._reports_and_analytics(tenant, demo_user, period, invoices, products)
        self._legacy_reports(demo_user, today)
        self._notifications(tenant, demo_user)

        self.stdout.write(self.style.SUCCESS("Enterprise demo environment seeded successfully."))
        self.stdout.write(f"Login user: {email}")
        self.stdout.write(f"Password: {password}")
        self.stdout.write(f"Tenant: {tenant.name}")

    def _user(self, *, email, username, mobile, first_name, last_name, password, full_access=False):
        user, _ = User.objects.update_or_create(
            email=email,
            defaults={
                "username": username,
                "mobile": mobile,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
                "is_staff": full_access,
                "is_superuser": full_access,
                "email_verified": True,
                "mobile_verified": True,
                "is_otp_verified": True,
                "role": "super_admin" if full_access else "customer",
                "primary_role": "owner" if full_access else "staff",
                "billing_access_level": "admin" if full_access else "user",
                "billing_role_type": "sub_user",
                "permissions_json": {"*": True, "demo_full_testing": full_access},
            },
        )
        user.set_password(password)
        user.save()
        return user

    def _grant_full_access(self, user, tenant):
        user.user_permissions.set(Permission.objects.all())
        for key in ["erp.full_access", "workforce.full_access", "reports.full_access", "tax.full_access", "execution.full_access"]:
            module, _ = DynamicModule.objects.update_or_create(tenant=tenant, key=key.split(".")[0], defaults={"label": key.split(".")[0].title(), "app_label": key.split(".")[0]})
            permission, _ = EnterprisePermission.objects.update_or_create(
                tenant=tenant,
                key=key,
                defaults={"module": module, "label": key, "scope": EnterprisePermission.Scope.ACTION, "is_active": True},
            )
            PermissionOverride.objects.update_or_create(tenant=tenant, user=user, permission=permission, defaults={"allowed": True, "reason": "Demo full testing access", "created_by": user})
        role, _ = EnterpriseRole.objects.update_or_create(tenant=tenant, key="demo-super-admin", defaults={"name": "Demo Super Admin", "is_system": True, "is_active": True})
        for permission in EnterprisePermission.objects.filter(tenant=tenant):
            RolePermission.objects.update_or_create(role=role, permission=permission, defaults={"allowed": True})

    def _branches(self, tenant, company):
        data = [
            ("HQ", "Lucknow HQ", "Hazratganj, Lucknow"),
            ("BST", "Basti Franchise Hub", "Station Road, Basti"),
            ("GKP", "Gorakhpur Distribution Hub", "Transport Nagar, Gorakhpur"),
        ]
        branches = []
        for code, name, address in data:
            branch, _ = Branch.objects.update_or_create(tenant=tenant, code=code, defaults={"company": company, "name": name, "address": address, "metadata": {"demo": True}})
            branches.append(branch)
        return branches

    def _org(self, tenant, company, branches):
        dept_data = [
            ("hr", "Human Resources"),
            ("accounts", "Accounts & GST"),
            ("sales", "Sales"),
            ("support", "Customer Support"),
            ("warehouse", "Warehouse"),
            ("marketing", "Digital Marketing"),
            ("delivery", "Delivery Operations"),
            ("remote", "Remote Workforce"),
        ]
        departments = {}
        for key, name in dept_data:
            departments[key], _ = Department.objects.update_or_create(tenant=tenant, key=key, defaults={"company": company, "branch": branches[0], "name": name, "cost_center": key.upper()})

        designations = {}
        for key, title, level in [
            ("company-admin", "Company Admin", 10),
            ("hr-manager", "HR Manager", 7),
            ("accountant", "Accountant", 6),
            ("sales-manager", "Sales Manager", 7),
            ("support-manager", "Support Manager", 7),
            ("warehouse-manager", "Warehouse Manager", 6),
            ("marketing-executive", "Marketing Executive", 4),
            ("delivery-staff", "Delivery Staff", 3),
            ("remote-executive", "Remote Executive", 4),
            ("freelancer", "Freelancer", 3),
            ("gig-worker", "Gig Worker", 2),
        ]:
            designations[key], _ = Designation.objects.update_or_create(tenant=tenant, key=key, defaults={"title": title, "level": level})

        teams = {}
        for key, dept_key, name in [
            ("hr-team", "hr", "HR Operations"),
            ("gst-team", "accounts", "GST & Ledger"),
            ("sales-north", "sales", "North Sales"),
            ("support-l1", "support", "L1 Support"),
            ("warehouse-shift-a", "warehouse", "Warehouse Shift A"),
            ("growth-team", "marketing", "Growth Marketing"),
        ]:
            teams[key], _ = Team.objects.update_or_create(tenant=tenant, key=key, defaults={"department": departments[dept_key], "name": name})
        return departments, designations, teams

    def _staff(self, tenant, company, branches, departments, designations, teams, demo_user, password):
        demo_profile, _ = EmployeeProfile.objects.update_or_create(
            tenant=tenant,
            employee_code="EMP-000",
            defaults={
                "user": demo_user,
                "worker_type": EmployeeProfile.WorkerType.EMPLOYEE,
                "lifecycle_status": EmployeeProfile.LifecycleStatus.ACTIVE,
                "company": company,
                "branch": branches[0],
                "department": departments["hr"],
                "designation": designations["company-admin"],
                "reporting_manager": demo_user,
                "joining_date": timezone.localdate() - timezone.timedelta(days=365),
                "salary_structure": {"ctc": 1200000, "basic": 65000, "hra": 25000},
                "incentive_model": {"type": "owner_demo", "full_testing": True},
                "permission_profile": {"role": "demo-super-admin", "demo_full_access": True, "all_modules": True},
                "metadata": {"profile_photo_url": "https://ui-avatars.com/api/?name=Demo+Test+3&background=0f766e&color=fff", "demo": True, "owner": True},
            },
        )
        people = [
            ("admin", "company-admin", "employee", "Aarav Company Admin", "hr"),
            ("hr", "hr-manager", "employee", "Neha HR Manager", "hr"),
            ("accounts", "accountant", "employee", "Rohit Accountant", "accounts"),
            ("sales", "sales-manager", "employee", "Priya Sales Manager", "sales"),
            ("support", "support-manager", "employee", "Kabir Support Manager", "support"),
            ("warehouse", "warehouse-manager", "employee", "Meera Warehouse Manager", "warehouse"),
            ("marketing", "marketing-executive", "employee", "Ananya Marketing", "marketing"),
            ("delivery", "delivery-staff", "delivery", "Imran Delivery Staff", "delivery"),
            ("remote", "remote-executive", "remote", "Sana Remote Executive", "remote"),
            ("freelancer", "freelancer", "freelancer", "Vikram Freelancer", "remote"),
            ("gig", "gig-worker", "gig", "Pooja Gig Worker", "delivery"),
        ]
        staff = [demo_profile]
        for index, (code, designation_key, worker_type, full_name, dept_key) in enumerate(people, start=1):
            first, *rest = full_name.split(" ")
            user = self._user(
                email=f"demo.{code}@example.com",
                username=f"demo_{code}",
                mobile=f"90000100{index:02d}",
                first_name=first,
                last_name=" ".join(rest),
                password=password,
                full_access=False,
            )
            profile, _ = EmployeeProfile.objects.update_or_create(
                tenant=tenant,
                employee_code=f"EMP-{index:03d}",
                defaults={
                    "user": user,
                    "worker_type": worker_type,
                    "lifecycle_status": EmployeeProfile.LifecycleStatus.ACTIVE,
                    "company": company,
                    "branch": branches[index % len(branches)],
                    "department": departments[dept_key],
                    "designation": designations[designation_key],
                    "reporting_manager": demo_user,
                    "joining_date": timezone.localdate() - timezone.timedelta(days=180 - index),
                    "salary_structure": {"ctc": 360000 + index * 45000, "basic": 18000 + index * 1500, "hra": 8000 + index * 500},
                    "incentive_model": {"type": "role_kpi", "monthly_target": 80 + index},
                    "permission_profile": {"role": designation_key, "demo_full_access": True},
                    "metadata": {"profile_photo_url": f"https://ui-avatars.com/api/?name={full_name.replace(' ', '+')}&background=2563eb&color=fff", "demo": True},
                },
            )
            TenantMembership.objects.update_or_create(tenant=tenant, user=user, defaults={"company": company, "branch": profile.branch, "is_active": True, "metadata": {"role": designation_key}})
            teams.get(f"{dept_key}-team", teams.get("hr-team")).members.add(user)
            staff.append(profile)
        return staff

    def _inventory(self, tenant, company, branches, today):
        warehouses = []
        for code, name, branch in [("MAIN", "Main Warehouse", branches[0]), ("COLD", "Cold Storage", branches[1]), ("DIST", "Distribution Warehouse", branches[2])]:
            wh, _ = Warehouse.objects.update_or_create(tenant=tenant, code=code, defaults={"company": company, "branch": branch, "name": name})
            warehouses.append(wh)
        ProductAttribute.objects.update_or_create(tenant=tenant, key="size", defaults={"name": "Size", "values": ["S", "M", "L", "XL", "8", "9"]})
        ProductAttribute.objects.update_or_create(tenant=tenant, key="flavour", defaults={"name": "Flavour", "values": ["Classic", "Masala", "Mint"]})
        product_data = [
            ("GROC-ATTA-10KG", "Premium Atta 10KG", "grocery", "goods", "KG"),
            ("PHAR-PARA-500", "Paracetamol 500mg Strip", "pharmacy", "goods", "strip"),
            ("REST-PANEER-MEAL", "Paneer Meal Combo", "restaurant", "goods", "plate"),
            ("GARM-SHIRT-M", "Cotton Shirt", "garment", "goods", "pcs"),
            ("FOOT-SHOE-9", "Running Shoe", "footwear", "goods", "pair"),
            ("DIST-OIL-15L", "Mustard Oil 15L", "distribution", "goods", "tin"),
        ]
        products, variants = [], []
        for index, (sku, name, category, product_type, uom) in enumerate(product_data, start=1):
            product, _ = Product.objects.update_or_create(tenant=tenant, sku=sku, defaults={"name": name, "category": category, "product_type": product_type, "uom": uom, "tax_code": "18"})
            variant, _ = ProductVariant.objects.update_or_create(
                tenant=tenant,
                sku=f"{sku}-STD",
                defaults={"product": product, "barcode": f"89000000{index:05d}", "attributes": {"variant": "Standard"}, "price": Decimal(99 + index * 140)},
            )
            StockLedgerEntry.objects.update_or_create(
                tenant=tenant,
                warehouse=warehouses[index % len(warehouses)],
                product=product,
                variant=variant,
                movement_type=StockLedgerEntry.MovementType.OPENING,
                reference_type="demo_seed",
                reference_id=sku,
                defaults={"quantity": Decimal(250 + index * 40), "unit_cost": Decimal(60 + index * 70), "batch_no": f"BATCH-{index:03d}", "expiry_date": today + timezone.timedelta(days=365 if category == "pharmacy" else 730)},
            )
            products.append(product)
            variants.append(variant)
        StockTransfer.objects.update_or_create(tenant=tenant, reference_no="ST-DEMO-001", defaults={"source_warehouse": warehouses[0], "destination_warehouse": warehouses[2], "status": "completed", "posted_at": timezone.now()})
        ProcurementRequest.objects.update_or_create(tenant=tenant, reference_no="PO-DEMO-001", defaults={"supplier_name": "Shakti Wholesale Suppliers", "status": "approval", "expected_at": timezone.now() + timezone.timedelta(days=3)})
        BillOfMaterials.objects.update_or_create(tenant=tenant, product=products[2], version=1, defaults={"output_quantity": 1, "components": [{"sku": "PANEER", "qty": 0.2}, {"sku": "GRAVY", "qty": 1}]})
        return warehouses, products, variants

    def _finance(self, tenant, user):
        accounts = {}
        for code, name, acc_type in [
            ("1000", "Cash", "asset"),
            ("1100", "Bank", "asset"),
            ("2000", "GST Payable", "liability"),
            ("4000", "Sales", "income"),
            ("5000", "Purchases", "expense"),
            ("5100", "Payroll Expense", "expense"),
        ]:
            accounts[code], _ = ChartOfAccount.objects.update_or_create(tenant=tenant, code=code, defaults={"name": name, "account_type": acc_type, "gst_applicable": code in {"2000", "4000", "5000"}})
        journal, _ = JournalEntry.objects.update_or_create(tenant=tenant, reference_no="JV-DEMO-SALES-001", defaults={"status": "posted", "narration": "Demo sales invoice posting", "posted_by": user})
        JournalLine.objects.update_or_create(journal=journal, account=accounts["1100"], defaults={"debit": Decimal("118000"), "credit": 0})
        JournalLine.objects.update_or_create(journal=journal, account=accounts["4000"], defaults={"debit": 0, "credit": Decimal("100000")})
        JournalLine.objects.update_or_create(journal=journal, account=accounts["2000"], defaults={"debit": 0, "credit": Decimal("18000")})
        return accounts

    def _tax_flow(self, tenant, user, today, accounts):
        slab, _ = GSTTaxSlab.objects.update_or_create(rate=Decimal("18.00"), cess_rate=0, defaults={"name": "GST 18%", "is_active": True})
        hsn, _ = HSNSACCode.objects.update_or_create(code="210690", code_type="hsn", defaults={"description": "Food preparations", "tax_slab": slab, "is_goods": True})
        payment, _ = PaymentQRProfile.objects.update_or_create(tenant=tenant, name="Billentra UPI Collection", defaults={"upi_id": "billentra@upi", "bank_name": "Demo Bank", "account_name": "Billentra Mega Retail", "account_number": "1234567890", "ifsc": "DEMO0001234", "payment_link": "upi://pay?pa=billentra@upi&pn=Billentra", "is_default": True, "metadata": {"qr_payload": "upi://pay?pa=billentra@upi&pn=Billentra"}})
        invoices = []
        for index in range(1, 9):
            buyer, _ = GSTParty.objects.update_or_create(
                tenant=tenant,
                name=f"Demo Customer {index}",
                party_type="customer",
                defaults={"gstin": f"09AAACC{index:04d}F1Z{index % 9}", "pan": f"AAACC{index:04d}F", "state_code": "09", "address": f"Customer Market {index}, UP", "pincode": "272001", "email": f"customer{index}@example.com", "phone": f"88888000{index:02d}"},
            )
            amount = Decimal(18000 + index * 9000)
            taxable = (amount / Decimal("1.18")).quantize(Decimal("0.01"))
            tax = (amount - taxable).quantize(Decimal("0.01"))
            inv, _ = GSTInvoice.objects.update_or_create(
                tenant=tenant,
                invoice_number=f"GST-DEMO-{index:04d}",
                defaults={
                    "invoice_date": today - timezone.timedelta(days=index),
                    "status": "eway_required" if amount > Decimal("50000") else "issued",
                    "seller_gstin": "09ABCDE1234F1Z5",
                    "seller_state_code": "09",
                    "buyer": buyer,
                    "place_of_supply_state_code": "09",
                    "subtotal": taxable,
                    "taxable_value": taxable,
                    "cgst_amount": (tax / 2).quantize(Decimal("0.01")),
                    "sgst_amount": (tax / 2).quantize(Decimal("0.01")),
                    "total_amount": amount,
                    "payment_profile": payment,
                    "source_type": "sales_order",
                    "source_id": f"SO-DEMO-{index:04d}",
                },
            )
            GSTInvoiceLine.objects.update_or_create(invoice=inv, description="Demo goods sale", defaults={"hsn_sac": hsn, "quantity": 10, "unit": "pcs", "unit_price": taxable / 10, "taxable_value": taxable, "tax_rate": 18, "cgst_amount": tax / 2, "sgst_amount": tax / 2, "total": amount})
            if amount > Decimal("50000"):
                EWayBillRequest.objects.update_or_create(
                    tenant=tenant,
                    invoice=inv,
                    defaults={"status": "ready", "transporter_name": "FastMove Logistics", "transporter_gstin": "09TRNSP1234F1Z9", "vehicle_number": "UP51AB1234", "distance_km": 145, "dispatch_address": "Lucknow HQ", "dispatch_pincode": "226001", "delivery_address": buyer.address, "delivery_pincode": buyer.pincode, "eway_ready_payload": {"invoice": inv.invoice_number, "amount": str(amount)}},
                )
            TaxValidationIssue.objects.update_or_create(tenant=tenant, invoice=inv, code=f"DEMO-GST-{index}", defaults={"message": "Demo GST validation passed", "severity": "info", "resolved_at": timezone.now()})
            TaxAuditLog.objects.update_or_create(tenant=tenant, invoice=inv, action="demo_invoice_generated", defaults={"actor": user, "after": {"total": str(amount)}})
            GSTLedgerEntry.objects.update_or_create(tenant=tenant, gstin=buyer.gstin, tax_type="cgst_sgst", period=today.strftime("%Y-%m"), defaults={"taxable_value": taxable, "tax_amount": tax, "metadata": {"invoice": inv.invoice_number}})
            invoices.append(inv)
        GSTReportSnapshot.objects.update_or_create(
            tenant=tenant,
            report_type="sales_register",
            period=today.strftime("%Y-%m"),
            defaults={
                "generated_by": user,
                "data": {
                    "summary": {"invoice_count": len(invoices), "taxable": "612000", "tax": "110160"},
                    "rows": [{"invoice": inv.invoice_number, "total": str(inv.total_amount)} for inv in invoices],
                },
            },
        )
        return invoices

    def _saas_partner_network(self, tenant, company, branches, staff, today):
        WhiteLabelProfile.objects.update_or_create(tenant=tenant, brand_name="Billentra Demo Cloud", defaults={"primary_color": "#2563eb", "secondary_color": "#0f172a", "accent_color": "#22c55e", "sidebar_config": {"mode": "enterprise"}, "module_config": {"all_modules": True}})
        plan, _ = SaaSPlan.objects.update_or_create(key="enterprise-demo-suite", defaults={"name": "Enterprise Demo Suite", "interval": "yearly", "base_price": 99999, "features": {"all": True}, "limits": {"users": 500}, "trial_days": 30})
        TenantSubscription.objects.update_or_create(tenant=tenant, plan=plan, defaults={"status": "active", "current_period_end": timezone.now() + timezone.timedelta(days=365), "payment_provider": "demo"})
        parent = None
        for code, ptype, name, branch in [
            ("SS-UP", "super_stockist", "UP Super Stockist", branches[0]),
            ("DIST-BST", "distributor", "Basti Distributor", branches[1]),
            ("DLR-GKP", "dealer", "Gorakhpur Dealer", branches[2]),
            ("RET-001", "retailer", "Retail Partner 001", branches[1]),
        ]:
            partner, _ = EcosystemPartner.objects.update_or_create(tenant=tenant, code=code, defaults={"parent": parent, "company": company, "branch": branch, "partner_type": ptype, "name": name, "contact_user": staff[3].user, "commission_rules": {"percent": 4 + len(code)}, "credit_limit": 250000, "territory": {"state": "UP"}})
            parent = partner
            if ptype in {"distributor", "dealer"}:
                FranchiseAgreement.objects.update_or_create(tenant=tenant, partner=partner, defaults={"royalty_percent": 3, "terms": {"demo": True}})
        RoutePlan.objects.update_or_create(tenant=tenant, code="ROUTE-BST-01", defaults={"name": "Basti Retail Beat", "owner": parent, "salesman": staff[7].user, "schedule": {"days": ["Mon", "Wed", "Fri"]}, "stops": [{"name": "Retailer A"}, {"name": "Retailer B"}]})

    def _workforce_flows(self, tenant, company, branches, departments, staff, user, period, today, now):
        shift, _ = Shift.objects.update_or_create(tenant=tenant, code="GEN", defaults={"name": "General Shift", "start_time": "09:30", "end_time": "18:30", "grace_minutes": 10, "overtime_after_minutes": 540})
        monthly, _ = PayrollPolicy.objects.update_or_create(tenant=tenant, name="Demo Monthly Salary", defaults={"pay_type": "hybrid", "base_amount": 35000, "hourly_rate": 250, "task_rate": 300, "commission_rules": {"sales_percent": 2}, "incentive_rules": {"kpi_bonus": 3000}, "deduction_rules": {"late_penalty": 100}, "tax_rules": {"tds_percent": 5}})
        run, _ = PayrollRun.objects.update_or_create(tenant=tenant, period=period, defaults={"status": "approval", "generated_by": user, "totals": {"gross": 0, "net": 0}})
        for index, employee in enumerate(staff, start=1):
            ShiftAssignment.objects.update_or_create(tenant=tenant, employee=employee, shift=shift, starts_at=today - timezone.timedelta(days=30), defaults={"ends_at": None})
            EmployeePayrollProfile.objects.update_or_create(tenant=tenant, employee=employee, defaults={"policy": monthly, "bank_name": "Demo Bank", "account_number": f"12345000{index:03d}", "ifsc": "DEMO0001234", "upi_id": f"{employee.employee_code.lower()}@upi"})
            for day in range(1, 8):
                base = timezone.make_aware(timezone.datetime.combine(today - timezone.timedelta(days=day), timezone.datetime.min.time()))
                AttendanceLog.objects.update_or_create(tenant=tenant, employee=employee, log_type="in", logged_at=base + timezone.timedelta(hours=9, minutes=28 + index % 9), defaults={"shift": shift, "method": "gps" if index % 2 else "biometric", "verification_status": "verified", "latitude": Decimal("26.8467"), "longitude": Decimal("80.9462")})
                AttendanceLog.objects.update_or_create(tenant=tenant, employee=employee, log_type="out", logged_at=base + timezone.timedelta(hours=18, minutes=35), defaults={"shift": shift, "method": "gps" if index % 2 else "biometric", "verification_status": "verified", "overtime_minutes": index % 4 * 10})
            LeaveRequest.objects.update_or_create(tenant=tenant, employee=employee, leave_type="casual", starts_on=today + timezone.timedelta(days=index), defaults={"ends_on": today + timezone.timedelta(days=index), "reason": "Demo personal leave", "status": "approval", "approver": user})
            StaffTask.objects.update_or_create(tenant=tenant, title=f"{employee.department.name} demo task", assignee=employee, defaults={"assigned_by": user, "description": "Complete production-like demo workflow", "status": "review", "priority": "high" if index % 3 == 0 else "medium", "due_at": now + timezone.timedelta(days=index)})
            StaffKPI.objects.update_or_create(tenant=tenant, employee=employee, key=f"kpi-{period}", period=period, defaults={"name": "Monthly Productivity KPI", "target_value": 100, "current_value": 70 + index * 2, "weight": 100})
            EmployeeActivityLog.objects.update_or_create(tenant=tenant, employee=employee, action="demo_activity", object_type="workflow", object_id=period, defaults={"payload": {"events": 35 + index}})
            ProductivitySignal.objects.update_or_create(tenant=tenant, employee=employee, signal_type="task", captured_at=now - timezone.timedelta(hours=index), defaults={"source": "demo", "score": 70 + index * 2, "duration_seconds": 18000, "evidence": {"tasks_completed": 4 + index}})
            EmployeeScoreSnapshot.objects.update_or_create(tenant=tenant, employee=employee, period=period, defaults={"productivity_score": 75 + index, "discipline_score": 85, "trust_score": 80 + index, "leadership_score": 60 + index, "communication_score": 78, "quality_score": 82, "fraud_risk_score": index % 3, "performance_score": 80 + index})
            gross = Decimal(30000 + index * 3000)
            slip, _ = Payslip.objects.update_or_create(tenant=tenant, payroll_run=run, employee=employee, defaults={"status": "approved", "gross_amount": gross, "incentive_amount": 2000 + index * 100, "overtime_amount": 500, "bonus_amount": 1000, "deduction_amount": 300, "tax_amount": gross * Decimal("0.05"), "net_amount": gross + Decimal(3200) - gross * Decimal("0.05"), "line_items": [{"label": "Basic", "amount": str(gross)}, {"label": "KPI incentive", "amount": str(2000 + index * 100)}]})
            PayoutInstruction.objects.update_or_create(tenant=tenant, payslip=slip, defaults={"method": "upi", "status": "queued", "destination": {"upi": f"{employee.employee_code.lower()}@upi"}})
            CognitiveEmployeeProfile.objects.update_or_create(tenant=tenant, employee=employee, defaults={"skills": ["ERP", employee.department.key, "customer_workflow"], "certifications": ["Billentra SOP"], "trust_score": 80 + index, "leadership_score": 58 + index, "engagement_score": 74 + index, "morale_score": 76, "burnout_risk": max(5, 35 - index), "promotion_probability": 55 + index, "ai_career_insights": {"next": "advanced certification"}})
            BehavioralSignal.objects.update_or_create(tenant=tenant, employee=employee, signal_type="engagement", captured_at=now - timezone.timedelta(days=index), defaults={"score": 75 + index, "confidence": 88, "source": "demo_survey"})
            EmployeeTransparencyRecord.objects.update_or_create(tenant=tenant, employee=employee, record_type="salary", period=period, defaults={"title": "Monthly salary calculation", "calculation": {"gross": str(gross), "net": str(slip.net_amount)}, "locked_at": now})
            EmployeeWallet.objects.update_or_create(tenant=tenant, employee=employee, defaults={"balance": 1200 + index * 200, "bonus_balance": 500, "reward_points": 100 + index})
        Announcement.objects.update_or_create(tenant=tenant, title="Demo payroll approval pending", defaults={"message": "Payroll run is ready for approval.", "created_by": user, "published_at": now})
        HRInsight.objects.update_or_create(tenant=tenant, title="Support team workload rising", insight_type="staffing", defaults={"confidence": 82, "recommendation": "Add one L1 support freelancer for evening shift.", "status": "open"})
        FraudRiskSignal.objects.update_or_create(tenant=tenant, employee=staff[-1], risk_type="suspicious_pattern", defaults={"risk_score": 18, "status": "open", "evidence": {"note": "Low risk demo alert"}})
        DisciplineCase.objects.update_or_create(tenant=tenant, employee=staff[-1], violation_type="late", defaults={"action": "warning", "severity": "low", "status": "review", "description": "Demo late attendance warning"})
        WorkforceProfitabilitySnapshot.objects.update_or_create(tenant=tenant, period=period, employee=staff[3], defaults={"revenue": 850000, "payroll_cost": 125000, "support_efficiency": 88, "sales_efficiency": 91, "roi": 6.8})

    def _execution_cloud(self, tenant, departments, staff, user, period, today, now):
        ToolAssignmentService().ensure_default_tools(tenant)
        UnifiedDashboardConfig.objects.update_or_create(tenant=tenant, key="default", defaults={"title": "Enterprise Demo Work Dashboard", "audience": {"all": True}, "widgets": ["tasks", "payroll", "attendance", "ai", "reports"], "layout": {"columns": 4}})
        project, _ = WorkProject.objects.update_or_create(tenant=tenant, name="Enterprise Demo Launch", defaults={"project_type": "implementation", "owner": staff[0], "department": departments["support"], "status": "active", "starts_at": now - timezone.timedelta(days=10), "due_at": now + timezone.timedelta(days=20)})
        board, _ = WorkBoard.objects.update_or_create(tenant=tenant, project=project, name="Demo Kanban", defaults={"board_type": "kanban", "columns": ["Draft", "Review", "Approval", "Completed"]})
        work_types = ["ticket", "bug", "lead", "approval", "delivery", "marketing", "finance", "task"]
        for index, employee in enumerate(staff, start=1):
            ToolAssignmentService().assign_for_employee(employee)
            item, _ = WorkItem.objects.update_or_create(
                tenant=tenant,
                title=f"{work_types[index % len(work_types)].title()} workflow #{index}",
                defaults={"project": project, "board": board, "work_type": work_types[index % len(work_types)], "description": "Interconnected demo work item", "status": "review" if index % 2 else "approval", "priority": "high" if index % 3 == 0 else "medium", "assignee": employee, "reporter": user, "due_at": now + timezone.timedelta(days=index), "sla_due_at": now + timezone.timedelta(hours=24 + index), "estimate_minutes": 240, "actual_minutes": 120 + index * 15, "source_type": "demo_flow", "source_id": f"FLOW-{index:03d}", "payload": {"interconnected": True}},
            )
            WorkComment.objects.update_or_create(tenant=tenant, work_item=item, author=user, message="Demo review comment", defaults={"visibility": "team"})
            WorkActivityRecord.objects.update_or_create(tenant=tenant, employee=employee, work_item=item, activity_type="work", started_at=now - timezone.timedelta(hours=index), defaults={"duration_seconds": 3600 + index * 300, "quality_score": 80 + index, "productivity_score": 78 + index, "fraud_risk_score": index % 4, "evidence": {"demo": True}})
        channel, _ = TeamChannel.objects.update_or_create(tenant=tenant, name="Enterprise Demo War Room", defaults={"channel_type": "project", "project": project, "config": {"realtime": True}})
        channel.members.set([employee for employee in staff[:6]])
        TeamMessage.objects.update_or_create(tenant=tenant, channel=channel, message="AI summary: demo workflows are ready for testing.", defaults={"sender": staff[0], "message_type": "ai_summary", "ai_summary": "All teams have active work, payroll, attendance, and reporting data."})
        for dtype in ["desktop", "mobile", "pos", "barcode", "biometric", "printer", "webcam", "gps"]:
            UniversalHardwareDevice.objects.update_or_create(tenant=tenant, fingerprint=f"DEMO-{dtype.upper()}", defaults={"device_type": dtype, "name": f"Demo {dtype.title()} Device", "assigned_employee": staff[0], "status": "active", "capabilities": ["demo", dtype], "last_seen_at": now})
        ExecutionCommandSnapshot.objects.update_or_create(tenant=tenant, period=today.strftime("%Y-%m-%d"), defaults={"live_employees": 8, "active_work_items": 22, "support_tickets": 6, "sales_activities": 9, "remote_sessions": 3, "field_locations": 5, "payroll_projection": 585000, "ai_alerts": 4, "workload_balance_score": 86, "payload": {"demo": True}})
        listing, _ = MarketplaceListing.objects.update_or_create(tenant=tenant, title="Need freelance support agents", defaults={"listing_type": "project", "description": "Evening support coverage", "budget_min": 12000, "budget_max": 35000, "requirements": {"skills": ["Hindi", "ERP", "Support"]}, "published_by": user})
        MarketplaceApplication.objects.update_or_create(tenant=tenant, listing=listing, agency_name="Demo Support Agency", defaults={"proposal": "We can provide 3 certified agents.", "quoted_amount": 28000, "status": "submitted"})
        partner, _ = PartnerProfile.objects.update_or_create(tenant=tenant, name="Demo Franchise Partner", partner_type="franchise", defaults={"owner": staff[3], "territory": {"city": "Basti"}, "commission_rules": {"percent": 8}, "revenue_share_rules": {"percent": 3}, "onboarding_status": "active"})
        PartnerSettlement.objects.update_or_create(tenant=tenant, partner=partner, period=period, defaults={"revenue": 450000, "commission": 36000, "revenue_share": 13500, "payable": 49500, "status": "review"})
        GigTask.objects.update_or_create(tenant=tenant, title="Verify 25 customer invoices", defaults={"gig_type": "micro", "status": "assigned", "required_skills": ["billing"], "payout_amount": 1500, "assignee": staff[-1], "assignment_score": 88})
        session, _ = RemoteWorkSession.objects.update_or_create(tenant=tenant, employee=staff[8], project_key="enterprise-demo", ended_at=None, defaults={"webcam_verified": True, "active_seconds": 14400, "idle_seconds": 900, "activity_score": 86, "authenticity_score": 93})
        RemoteActivityEvent.objects.update_or_create(tenant=tenant, session=session, event_type="screenshot", captured_at=now, defaults={"payload": {"window": "ERP Demo"}, "risk_score": 2})

    def _platform_metadata(self, tenant, user):
        for industry in ["grocery", "pharmacy", "restaurant", "garment", "footwear", "distribution"]:
            blueprint, _ = IndustryBlueprint.objects.update_or_create(tenant=tenant, key=f"{industry}-demo", defaults={"name": f"{industry.title()} Demo Blueprint", "industry": industry, "description": f"Demo {industry} workflow", "configuration": {"demo": True}})
            module, _ = ModuleDefinition.objects.update_or_create(tenant=tenant, key=f"{industry}-ops", defaults={"name": f"{industry.title()} Operations", "domain": industry, "blueprint": blueprint, "schema": {"demo": True}})
            MenuItem.objects.update_or_create(tenant=tenant, key=f"menu-{industry}", defaults={"module": module, "label": f"{industry.title()} Dashboard", "url": f"/demo/{industry}/", "sort_order": 20})
            form, _ = FormDefinition.objects.update_or_create(tenant=tenant, key=f"{industry}-order-form", defaults={"module": module, "name": f"{industry.title()} Order Form", "model_path": "demo.order", "layout": {"columns": 2}, "validation_schema": {"required": ["customer", "items"]}})
            FormFieldDefinition.objects.update_or_create(form=form, key="customer", defaults={"label": "Customer", "field_type": "text", "sort_order": 1, "is_required": True})
            workflow, _ = WorkflowDefinition.objects.update_or_create(tenant=tenant, key=f"{industry}-approval", defaults={"module": module, "name": f"{industry.title()} Approval Workflow", "applies_to": "demo.order", "start_state": "draft"})
            for order, state in enumerate(["draft", "review", "approval", "completed", "cancelled"], start=1):
                WorkflowState.objects.update_or_create(workflow=workflow, key=state, defaults={"label": state.title(), "state_type": "terminal" if state in {"completed", "cancelled"} else "normal", "sort_order": order})
            WorkflowTransition.objects.update_or_create(workflow=workflow, key="submit-for-approval", defaults={"label": "Submit for Approval", "from_state": "review", "to_state": "approval", "actions": [{"type": "notify"}]})
            ReportDefinition.objects.update_or_create(tenant=tenant, module=module, key=f"{industry}-kpi-report", defaults={"name": f"{industry.title()} KPI Report", "report_type": "chart", "query_spec": {"source": industry}, "columns": ["date", "sales", "margin"], "filters": ["date_range"]})
        for key in ["dynamic_dashboards", "ai_copilot", "offline_pwa", "hardware_layer", "realtime_command_center"]:
            FeatureToggle.objects.update_or_create(tenant=tenant, key=key, defaults={"name": key.replace("_", " ").title(), "enabled": True, "conditions": {"demo": True}})
        AutomationRule.objects.update_or_create(tenant=tenant, key="low-stock-demo", defaults={"name": "Low Stock Reorder Suggestion", "trigger_event": "stock_low", "status": "active", "run_as": user, "conditions": {"stock_lt": 20}, "actions": [{"type": "create_procurement"}]})
        EventSubscription.objects.update_or_create(tenant=tenant, event_type="invoice_created", name="Demo invoice automation", defaults={"handler_type": "notification", "handler_config": {"channels": ["ui", "email", "whatsapp"]}})
        BackgroundJobDefinition.objects.update_or_create(tenant=tenant, key="demo-report-export", defaults={"name": "Demo Report Export", "task_path": "reports.tasks.export_demo_report", "queue": "reports", "schedule": {"daily": "20:00"}})

    def _reports_and_analytics(self, tenant, user, period, invoices, products):
        categories = {}
        for key, name in [("sales", "Sales"), ("gst", "GST"), ("payroll", "Payroll"), ("inventory", "Inventory"), ("workforce", "Workforce"), ("franchise", "Franchise")]:
            categories[key], _ = ReportCategory.objects.update_or_create(key=f"demo-{key}", defaults={"name": f"Demo {name}", "sort_order": 10})
        report_specs = [
            ("demo-sales-register", "Demo Sales Register", "sales", "table"),
            ("demo-gst-summary", "Demo GST Summary", "gst", "statement"),
            ("demo-payroll-report", "Demo Payroll Report", "payroll", "table"),
            ("demo-stock-ageing", "Demo Stock Ageing", "inventory", "chart"),
            ("demo-productivity", "Demo Employee Productivity", "workforce", "chart"),
            ("demo-franchise-analytics", "Demo Franchise Analytics", "franchise", "kpi"),
        ]
        for key, name, domain, rtype in report_specs:
            template, _ = ReportTemplate.objects.update_or_create(tenant=tenant, key=key, defaults={"name": name, "domain": domain, "report_type": rtype, "category": categories[domain], "source_model": "demo", "columns": ["date", "name", "amount", "status"], "filters": [{"key": "date_range"}, {"key": "branch"}], "chart_spec": {"type": "bar"}})
            SavedReportFilter.objects.update_or_create(tenant=tenant, template=template, user=user, name="Default Demo Filter", defaults={"filters": {"period": period}, "is_default": True})
            run, _ = ReportRun.objects.update_or_create(tenant=tenant, template=template, user=user, filters={"period": period}, defaults={"status": "success", "row_count": 25, "duration_ms": 320, "result_preview": {"rows": [{"label": name, "value": 100}]}})
            ReportExport.objects.update_or_create(tenant=tenant, run=run, export_format="pdf", defaults={"status": "ready", "payload": {"download": True, "demo": True}})
        metrics = [
            ("sales_today", "Sales Today", "sales", 185000),
            ("gst_payable", "GST Payable", "gst", 33300),
            ("payroll_projection", "Payroll Projection", "payroll", 585000),
            ("stock_value", "Stock Value", "inventory", 2450000),
            ("employee_productivity", "Employee Productivity", "workforce", 86),
            ("franchise_roi", "Franchise ROI", "franchise", 6.7),
            ("ai_fraud_risk", "AI Fraud Risk", "ai", 3),
        ]
        for key, name, domain, value in metrics:
            AnalyticsMetric.objects.update_or_create(tenant=tenant, key=key, period=period, defaults={"name": name, "domain": domain, "value": Decimal(str(value)), "dimension": {"demo": True}})
            RealtimeDashboardCounter.objects.update_or_create(tenant=tenant, key=key, defaults={"name": name, "value": Decimal(str(value)), "channel": "demo"})
        dashboard, _ = DashboardDefinition.objects.update_or_create(tenant=tenant, key="demo-enterprise-command", defaults={"name": "Demo Enterprise Command Center", "layout": {"columns": 4}, "filters": ["branch", "period"]})
        for index, (key, name, domain, value) in enumerate(metrics, start=1):
            DashboardWidget.objects.update_or_create(dashboard=dashboard, key=key, defaults={"title": name, "widget_type": "kpi", "data_source": {"metric": key}, "layout": {"x": index % 4, "y": index // 4}, "sort_order": index})

    def _notifications(self, tenant, user):
        for index, (title, body, level) in enumerate(
            [
                ("Payroll approval pending", "Demo payroll run requires approval.", "warning"),
                ("Low stock alert", "Mustard Oil 15L is close to reorder threshold.", "warning"),
                ("GST invoice issued", "GST-DEMO-0005 has e-way bill ready data.", "success"),
                ("Support SLA risk", "Two support tickets are nearing SLA breach.", "error"),
                ("AI insight ready", "Workforce productivity forecast generated.", "info"),
            ],
            start=1,
        ):
            Notification.objects.update_or_create(user=user, title=title, defaults={"body": body, "level": level, "data": {"demo": True, "priority": index}})
            SmartNotification.objects.update_or_create(
                tenant=tenant,
                user=user,
                title=title,
                defaults={"message": body, "severity": "critical" if level == "error" else level, "status": "unread", "action_url": "/accounts/dashboard/", "metadata": {"demo": True}},
            )
        AuditLog.objects.create(tenant=tenant, user=user, action="demo_seed_completed", object_type="enterprise_demo", object_id="billentra-enterprise-demo", after={"status": "ready"}, metadata={"demo": True})

    def _legacy_reports(self, user, today):
        customers = []
        for index in range(1, 7):
            party, _ = Party.objects.update_or_create(
                owner=user,
                name=f"Demo Retail Customer {index}",
                defaults={
                    "mobile": f"77777000{index:02d}",
                    "email": f"retail.customer{index}@example.com",
                    "gst": f"09DEMO{index:04d}F1Z{index % 9}",
                    "address": f"Demo Customer Market {index}, Uttar Pradesh",
                    "pincode_text": "272001",
                    "party_type": "customer",
                    "upi_id": f"customer{index}@upi",
                    "is_premium": True,
                    "credit_score": 75 + index,
                    "total_due": Decimal(25000 + index * 4000),
                    "customer_category": "Demo Retail",
                },
            )
            customers.append(party)
        suppliers = []
        for index in range(1, 4):
            supplier, _ = Party.objects.update_or_create(
                owner=user,
                name=f"Demo Supplier {index}",
                defaults={
                    "mobile": f"76666000{index:02d}",
                    "email": f"supplier{index}@example.com",
                    "gst": f"09SUPP{index:04d}F1Z{index % 9}",
                    "address": f"Supplier Industrial Area {index}",
                    "party_type": "supplier",
                    "credit_period": 30,
                    "opening_balance": Decimal(40000 + index * 10000),
                },
            )
            suppliers.append(supplier)

        modes = ["cash", "upi", "bank", "online"]
        for day in range(0, 120, 8):
            txn_date = today - timezone.timedelta(days=day)
            for index, party in enumerate(customers, start=1):
                amount = Decimal(3500 + index * 1250 + day * 11)
                Transaction.objects.update_or_create(
                    party=party,
                    txn_type="credit",
                    date=txn_date,
                    notes=f"Demo sales invoice payment {txn_date}",
                    defaults={"txn_mode": modes[index % len(modes)], "amount": amount, "gst_type": "gst"},
                )
            for index, supplier in enumerate(suppliers, start=1):
                amount = Decimal(2200 + index * 1800 + day * 9)
                Transaction.objects.update_or_create(
                    party=supplier,
                    txn_type="debit",
                    date=txn_date,
                    notes=f"Demo purchase payment {txn_date}",
                    defaults={"txn_mode": modes[index % len(modes)], "amount": amount, "gst_type": "gst"},
                )
        for party in customers + suppliers:
            credit = party.transactions.filter(txn_type="credit").aggregate(total=Sum("amount"))["total"] or Decimal("0")
            debit = party.transactions.filter(txn_type="debit").aggregate(total=Sum("amount"))["total"] or Decimal("0")
            CreditAccount.objects.update_or_create(
                party=party,
                user=user,
                defaults={"credit_limit": Decimal("250000"), "outstanding": max(Decimal("0"), credit - debit)},
            )

        categories = {}
        for name in ["Grocery", "Pharmacy", "Restaurant", "Garment", "Footwear", "Distribution"]:
            categories[name], _ = Category.objects.update_or_create(owner=user, name=f"Demo {name}", defaults={"description": f"Demo {name} category"})
        warehouse, _ = CommerceWarehouse.objects.update_or_create(name="Demo Main Store", defaults={"location": "Lucknow", "capacity": 10000})
        product_specs = [
            ("RPT-GROC-ATTA", "Report Demo Atta 10KG", "Grocery", 599, 30, 12),
            ("RPT-PHAR-PARA", "Report Demo Paracetamol", "Pharmacy", 42, 40, 9),
            ("RPT-REST-MEAL", "Report Demo Meal Combo", "Restaurant", 249, 20, 60),
            ("RPT-GARM-SHIRT", "Report Demo Cotton Shirt", "Garment", 899, 6, 18),
            ("RPT-FOOT-SHOE", "Report Demo Running Shoe", "Footwear", 1499, 15, 5),
            ("RPT-DIST-OIL", "Report Demo Mustard Oil", "Distribution", 1999, 18, 45),
        ]
        commerce_products = []
        for sku, name, category, price, min_stock, stock in product_specs:
            product, _ = CommerceProduct.objects.update_or_create(
                sku=sku,
                defaults={"owner": user, "name": name, "category": categories[category], "price": Decimal(price), "stock": stock, "min_stock": min_stock, "unit": "pcs", "hsn_code": "210690", "gst_rate": Decimal("18.00")},
            )
            commerce_products.append(product)
            StockEntry.objects.update_or_create(product=product, entry_type="IN", date=today - timezone.timedelta(days=45), defaults={"quantity": Decimal(stock + 40)})
            StockEntry.objects.update_or_create(product=product, entry_type="OUT", date=today - timezone.timedelta(days=3), defaults={"quantity": Decimal(max(1, 40 - stock))})
        for index, party in enumerate(customers[:4], start=1):
            quote, _ = Quotation.objects.update_or_create(
                party=party,
                quotation_number=f"DEMO-QTN-{index:04d}",
                defaults={"date": today - timezone.timedelta(days=index), "valid_till": today + timezone.timedelta(days=15), "status": "approved" if index % 2 else "sent", "total_amount": Decimal(25000 + index * 6500), "remarks": "Demo quotation for report testing", "warehouse": warehouse, "created_by": user},
            )
            product = commerce_products[index % len(commerce_products)]
            QuotationItem.objects.update_or_create(quotation=quote, product=product, defaults={"warehouse": warehouse, "qty": 5 + index, "rate": product.price, "tax": Decimal("18"), "total": product.price * Decimal(5 + index)})

        yesterday = today - timezone.timedelta(days=1)
        Transaction.objects.update_or_create(
            party=customers[0],
            txn_type="credit",
            date=yesterday,
            notes="Demo day-book sales entry",
            defaults={"txn_mode": "cash", "amount": Decimal("12500.00"), "gst_type": "gst"},
        )
        Transaction.objects.update_or_create(
            party=suppliers[0],
            txn_type="debit",
            date=yesterday,
            notes="Demo day-book purchase entry",
            defaults={"txn_mode": "bank", "amount": Decimal("4200.00"), "gst_type": "gst"},
        )
