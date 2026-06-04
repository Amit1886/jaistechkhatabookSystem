from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django import template
from django.contrib import admin
from django.urls import NoReverseMatch, reverse

register = template.Library()


@dataclass(frozen=True)
class MenuItemSpec:
    label: str
    models: tuple[str, ...]
    icon: str = "dot"


@dataclass(frozen=True)
class MenuGroupSpec:
    title: str
    icon: str
    keywords: tuple[str, ...]
    items: tuple[MenuItemSpec, ...]


GROUPS: tuple[MenuGroupSpec, ...] = (
    MenuGroupSpec("User Management", "UM", ("user", "profile", "session", "device", "activity", "login"), (
        MenuItemSpec("Users", ("accounts.user", "auth.user", "users.user"), "US"),
        MenuItemSpec("User Profiles", ("accounts.userprofile", "khataapp.profile", "users.profile"), "UP"),
        MenuItemSpec("Login History", ("accounts.loginlog", "users.loginlog"), "LH"),
        MenuItemSpec("Sessions", ("sessions.session",), "SE"),
        MenuItemSpec("User Activity", ("accounts.useractivity", "enterprise_control.auditlog"), "UA"),
        MenuItemSpec("User Devices", ("enterprise_control.devicesession", "mobileapi.device"), "UD"),
    )),
    MenuGroupSpec("Permission Management", "PM", ("permission", "access", "policy"), (
        MenuItemSpec("Permissions", ("auth.permission", "saas.permissionnode"), "PR"),
        MenuItemSpec("Permission Groups", ("auth.group",), "PG"),
        MenuItemSpec("Access Policies", ("enterprise_control.permissiontemplate", "saas.userpermissiongraph"), "AP"),
        MenuItemSpec("Screen Permissions", ("core_settings.settingpermission",), "SP"),
        MenuItemSpec("API Permissions", ("core_settings.apipermission", "api_integrations.apikey"), "AK"),
    )),
    MenuGroupSpec("Role Management", "RM", ("role", "hierarchy"), (
        MenuItemSpec("Roles", ("saas.roletemplate", "accounts.role"), "RO"),
        MenuItemSpec("Role Assignment", ("enterprise_control.userworkspace", "saas.userpermissiongraph"), "RA"),
        MenuItemSpec("Role Policies", ("enterprise_control.permissiontemplate",), "RP"),
        MenuItemSpec("Role Hierarchy", ("hierarchy.hierarchynode", "saas.rolehierarchy"), "RH"),
    )),
    MenuGroupSpec("OTP Management", "OM", ("otp",), (
        MenuItemSpec("OTP Logs", ("accounts.otplog", "users.otplog"), "OL"),
        MenuItemSpec("OTP Providers", ("accounts.otpprovider", "sms_center.smsgateway"), "OP"),
        MenuItemSpec("OTP Settings", ("core_settings.settingvalue", "core.enterprisesetting"), "OS"),
    )),
    MenuGroupSpec("Settings Management", "SM", ("setting", "theme", "branding", "smtp", "firebase"), (
        MenuItemSpec("General Settings", ("core.enterprisesetting", "core_settings.companysettings"), "GS"),
        MenuItemSpec("System Settings", ("core_settings.saassettings", "system_mode.systemmode"), "SS"),
        MenuItemSpec("App Settings", ("core_settings.appsettings", "enterprise_control.workspace"), "AS"),
        MenuItemSpec("Security Settings", ("core_settings.settingpermission",), "SC"),
        MenuItemSpec("Branding Settings", ("enterprise_control.themeconfig", "core_settings.uisettings"), "BR"),
        MenuItemSpec("Theme Settings", ("enterprise_control.themeconfig",), "TH"),
        MenuItemSpec("API Settings", ("api_integrations.integrationcredential", "core.enterprisesetting"), "AI"),
        MenuItemSpec("SMTP Settings", ("core.enterprisesetting",), "ST"),
        MenuItemSpec("Firebase Settings", ("core.enterprisesetting",), "FB"),
        MenuItemSpec("WhatsApp Settings", ("whatsapp.whatsappaccount", "core.enterprisesetting"), "WA"),
        MenuItemSpec("SMS Settings", ("sms_center.smsgateway", "core.enterprisesetting"), "SMS"),
        MenuItemSpec("Payment Settings", ("billing.paymentgateway", "payments.paymentgateway"), "PY"),
    )),
    MenuGroupSpec("Services Management", "SV", ("service", "plan", "pricing"), (
        MenuItemSpec("Services", ("enterprise_control.dynamicmodule", "subscription.service"), "SV"),
        MenuItemSpec("Service Plans", ("billing.plan", "subscription.plan"), "PL"),
        MenuItemSpec("Service Categories", ("products.category", "commerce.category"), "CA"),
        MenuItemSpec("Service Pricing", ("billing.planfeature", "billing.planpermissions"), "PC"),
    )),
    MenuGroupSpec("Features Management", "FM", ("feature", "toggle", "visibility"), (
        MenuItemSpec("Features", ("billing.featureregistry", "core_settings.featuresettings"), "FE"),
        MenuItemSpec("Feature Access", ("billing.userfeatureoverride", "billing.planfeature"), "FA"),
        MenuItemSpec("Feature Visibility", ("core_settings.featuresettings",), "FV"),
        MenuItemSpec("Feature Toggles", ("billing.featuretoggle",), "FT"),
    )),
    MenuGroupSpec("App Management", "AM", ("app", "mobile", "launcher", "button", "navigation", "layout", "module"), (
        MenuItemSpec("Mobile Apps", ("mobileapi.mobileapp", "enterprise_control.dynamicmodule"), "MA"),
        MenuItemSpec("App Launcher", ("enterprise_control.dynamicmodule",), "AL"),
        MenuItemSpec("App Buttons", ("enterprise_control.dynamicbutton",), "AB"),
        MenuItemSpec("App Navigation", ("enterprise_control.dynamicmenuitem",), "AN"),
        MenuItemSpec("App Layouts", ("enterprise_control.workspace", "enterprise_control.dashboardwidget"), "LY"),
    )),
    MenuGroupSpec("Web Management", "WM", ("website", "page", "seo", "storefront", "landing"), (
        MenuItemSpec("Website Pages", ("core_settings.landingpagesettings", "storefront.storepage"), "WP"),
        MenuItemSpec("Website Menus", ("enterprise_control.dynamicmenuitem", "storefront.storefrontmenu"), "MN"),
        MenuItemSpec("Website Themes", ("enterprise_control.themeconfig",), "WT"),
        MenuItemSpec("Website SEO", ("storefront.seosetting", "core_settings.landingmarketingfeature"), "SEO"),
    )),
    MenuGroupSpec("POS Management", "POS", ("pos", "counter", "terminal"), (
        MenuItemSpec("POS Devices", ("enterprise_control.devicesession", "pos.posdevice"), "PD"),
        MenuItemSpec("POS Billing", ("pos.sale", "billing.billinginvoice"), "PB"),
        MenuItemSpec("POS Counters", ("pos.counter",), "PC"),
        MenuItemSpec("POS Orders", ("orders.order", "commerce.order"), "PO"),
        MenuItemSpec("POS Payments", ("billing.payment", "payments.payment"), "PP"),
        MenuItemSpec("POS Settings", ("core.enterprisesetting", "printer_config.printerprofile"), "PS"),
    )),
    MenuGroupSpec("SelfCheckout Management", "SC", ("selfcheckout", "kiosk"), (
        MenuItemSpec("SelfCheckout Devices", ("selfcheckout.kioskdevice", "enterprise_control.devicesession"), "SD"),
        MenuItemSpec("SelfCheckout Orders", ("selfcheckout.selfcheckoutorder", "orders.order"), "SO"),
        MenuItemSpec("Kiosk Settings", ("selfcheckout.kiosksetting", "core.enterprisesetting"), "KS"),
        MenuItemSpec("QR Payments", ("payments.payment", "billing.payment"), "QR"),
    )),
    MenuGroupSpec("Report Management", "RP", ("report", "export", "schedule"), (
        MenuItemSpec("Reports", ("reports.report", "apps.platform.reporting.reportdefinition"), "RE"),
        MenuItemSpec("Report Builder", ("enterprise_control.dashboardwidget", "reports.query"), "RB"),
        MenuItemSpec("Report Exports", ("reports.reportexport",), "RX"),
        MenuItemSpec("Scheduled Reports", ("reports.scheduledreport",), "SR"),
    )),
    MenuGroupSpec("Analytics Management", "AN", ("analytics", "bi", "insight"), (
        MenuItemSpec("Analytics Dashboard", ("analytics.analyticsdashboard", "smart_bi.dashboard"), "AD"),
        MenuItemSpec("Sales Analytics", ("analytics.salesanalytics", "smart_bi.report"), "SA"),
        MenuItemSpec("Customer Analytics", ("analytics.customeranalytics",), "CA"),
        MenuItemSpec("Device Analytics", ("performance.performancemetric",), "DA"),
    )),
    MenuGroupSpec("API Management", "API", ("api", "webhook", "integration", "rate"), (
        MenuItemSpec("API Keys", ("api_integrations.apikey", "api_integrations.integrationcredential"), "AK"),
        MenuItemSpec("API Logs", ("api_integrations.apilog", "enterprise_control.auditlog"), "LG"),
        MenuItemSpec("API Access", ("enterprise_control.permissiontemplate",), "AA"),
        MenuItemSpec("API Rate Limits", ("core_settings.settingvalue",), "RL"),
        MenuItemSpec("Webhooks", ("api_integrations.webhook", "whatsapp.webhookevent"), "WH"),
    )),
    MenuGroupSpec("SaaS Management", "SAAS", ("saas", "tenant", "subscription", "usage"), (
        MenuItemSpec("Subscription Plans", ("billing.plan", "subscription.subscriptionplan"), "SP"),
        MenuItemSpec("Tenants", ("saas.tenant", "apps.platform.saas_ecosystem.tenant"), "TE"),
        MenuItemSpec("Tenant Billing", ("billing.subscription", "billing.billinginvoice"), "TB"),
        MenuItemSpec("Usage Logs", ("performance.performancemetric", "enterprise_control.auditlog"), "UL"),
    )),
    MenuGroupSpec("WhiteLabel Management", "WL", ("whitelabel", "brand", "domain"), (
        MenuItemSpec("WhiteLabel Clients", ("saas.whitelabelclient", "vendors.vendor"), "WC"),
        MenuItemSpec("Branding", ("enterprise_control.themeconfig",), "BR"),
        MenuItemSpec("Domains", ("vendors.vendordomain", "saas.domain"), "DM"),
        MenuItemSpec("App Branding", ("enterprise_control.themeconfig",), "AB"),
    )),
    MenuGroupSpec("Domain URL Management", "DU", ("domain", "url", "ssl", "redirect"), (
        MenuItemSpec("Domains", ("vendors.vendordomain", "saas.domain"), "DO"),
        MenuItemSpec("URLs", ("storefront.storeurl", "core_settings.settingvalue"), "URL"),
        MenuItemSpec("SSL Settings", ("core.enterprisesetting",), "SSL"),
        MenuItemSpec("Redirects", ("storefront.redirectrule",), "RD"),
    )),
    MenuGroupSpec("IP Management", "IP", ("ip", "device", "security"), (
        MenuItemSpec("Allowed IPs", ("core_settings.settingpermission",), "AI"),
        MenuItemSpec("Blocked IPs", ("fraud_detection.blockedip",), "BI"),
        MenuItemSpec("Device IP Logs", ("enterprise_control.devicesession",), "DL"),
    )),
    MenuGroupSpec("Expenses Management", "EX", ("expense",), (
        MenuItemSpec("Expenses", ("accounts.expense", "khataapp.expense"), "EX"),
        MenuItemSpec("Expense Categories", ("accounts.expensecategory",), "EC"),
        MenuItemSpec("Expense Reports", ("reports.report",), "ER"),
    )),
    MenuGroupSpec("Sales Management", "SL", ("sale", "order", "invoice", "transaction", "payment"), (
        MenuItemSpec("Sales", ("commerce.sale", "pos.sale"), "SA"),
        MenuItemSpec("Orders", ("orders.order", "commerce.order"), "OR"),
        MenuItemSpec("Invoices", ("billing.billinginvoice", "commerce.invoice"), "IN"),
        MenuItemSpec("Transactions", ("khataapp.transaction", "ledger.transaction"), "TR"),
        MenuItemSpec("Payments", ("billing.payment", "payments.payment"), "PY"),
    )),
    MenuGroupSpec("Agents Management", "AG", ("agent", "commission"), (
        MenuItemSpec("Agents", ("accounts.agent", "users.agent"), "AG"),
        MenuItemSpec("Agent Commissions", ("commission.commission",), "AC"),
        MenuItemSpec("Agent Performance", ("commission.commissionstatement", "performance.performancemetric"), "AP"),
    )),
    MenuGroupSpec("E-Commerce Management", "EC", ("ecommerce", "store", "coupon", "delivery"), (
        MenuItemSpec("Online Orders", ("storefront.storeorder", "orders.order"), "OO"),
        MenuItemSpec("Delivery", ("delivery.delivery", "delivery.deliveryassignment"), "DL"),
        MenuItemSpec("Coupons", ("auto_discount.discountcampaign", "storefront.coupon"), "CP"),
        MenuItemSpec("Online Payments", ("payments.payment", "billing.payment"), "OP"),
    )),
    MenuGroupSpec("Vendor Management", "VN", ("vendor",), (
        MenuItemSpec("Vendors", ("vendors.vendor",), "VE"),
        MenuItemSpec("Vendor Payments", ("vendors.vendorpayment", "payments.payment"), "VP"),
        MenuItemSpec("Vendor Products", ("vendors.vendorproduct", "products.product"), "PR"),
    )),
    MenuGroupSpec("Customer & Party Management", "CP", ("customer", "party", "ledger"), (
        MenuItemSpec("Customers", ("crm.customer", "smart_khata.customer"), "CU"),
        MenuItemSpec("Parties", ("khataapp.party", "ledger.party"), "PA"),
        MenuItemSpec("Customer Ledger", ("ledger.ledgeraccount", "khataapp.transaction"), "CL"),
        MenuItemSpec("Customer Transactions", ("khataapp.transaction", "ledger.transaction"), "CT"),
    )),
    MenuGroupSpec("Supplier Management", "SU", ("supplier", "procurement"), (
        MenuItemSpec("Suppliers", ("procurement.supplier", "vendors.vendor"), "SU"),
        MenuItemSpec("Supplier Ledger", ("ledger.ledgeraccount",), "SL"),
        MenuItemSpec("Supplier Orders", ("procurement.purchaseorder", "commerce.purchaseorder"), "SO"),
    )),
    MenuGroupSpec("Staff Management", "ST", ("staff", "attendance", "payroll", "workforce"), (
        MenuItemSpec("Staff", ("apps.platform.workforce.staff", "users.staff"), "ST"),
        MenuItemSpec("Attendance", ("apps.platform.workforce.attendance",), "AT"),
        MenuItemSpec("Payroll", ("apps.platform.workforce.payroll",), "PR"),
        MenuItemSpec("Staff Permissions", ("saas.userpermissiongraph",), "SP"),
    )),
    MenuGroupSpec("Company Management", "CO", ("company", "branch"), (
        MenuItemSpec("Companies", ("accounts.company", "apps.platform.core.company"), "CO"),
        MenuItemSpec("Company Branches", ("accounts.branch", "apps.platform.core.branch"), "CB"),
        MenuItemSpec("Company Settings", ("core_settings.companysettings", "core.enterprisesetting"), "CS"),
    )),
    MenuGroupSpec("Profile Management", "PF", ("profile", "account"), (
        MenuItemSpec("Profiles", ("accounts.profile", "users.profile"), "PF"),
        MenuItemSpec("Profile Settings", ("core.enterprisesetting",), "PS"),
        MenuItemSpec("Account Security", ("enterprise_control.devicesession", "core_settings.settingpermission"), "AS"),
    )),
    MenuGroupSpec("Category Management", "CAT", ("category", "tag", "brand"), (
        MenuItemSpec("Categories", ("products.category", "commerce.category"), "CA"),
        MenuItemSpec("Subcategories", ("products.subcategory", "commerce.subcategory"), "SC"),
        MenuItemSpec("Tags", ("products.tag", "storefront.tag"), "TG"),
    )),
    MenuGroupSpec("WhatsApp Management", "WA", ("whatsapp",), (
        MenuItemSpec("WhatsApp API", ("whatsapp.whatsappaccount", "whatsapp_gateway.whatsappgateway"), "WA"),
        MenuItemSpec("WhatsApp Templates", ("whatsapp.whatsapptemplate",), "WT"),
        MenuItemSpec("WhatsApp Logs", ("whatsapp.whatsapplog", "whatsapp_gateway.whatsappmessage"), "WL"),
    )),
    MenuGroupSpec("SMS Management", "SMS", ("sms",), (
        MenuItemSpec("SMS Gateway", ("sms_center.smsgateway",), "SG"),
        MenuItemSpec("SMS Templates", ("sms_center.smstemplate",), "ST"),
        MenuItemSpec("SMS Logs", ("sms_center.smslog",), "SL"),
    )),
    MenuGroupSpec("Email Management", "EM", ("email", "smtp"), (
        MenuItemSpec("Email Templates", ("notifications.emailtemplate",), "ET"),
        MenuItemSpec("SMTP", ("core.enterprisesetting",), "SM"),
        MenuItemSpec("Email Logs", ("notifications.emaillog",), "EL"),
    )),
    MenuGroupSpec("Billing Management", "BI", ("billing", "gst", "tax", "invoice", "payment"), (
        MenuItemSpec("Billing", ("billing.subscription", "billing.billinginvoice"), "BI"),
        MenuItemSpec("GST", ("apps.platform.tax_compliance.gstfiling",), "GST"),
        MenuItemSpec("Taxes", ("apps.platform.tax_compliance.taxrule",), "TX"),
        MenuItemSpec("Invoices", ("billing.billinginvoice", "commerce.invoice"), "IN"),
        MenuItemSpec("Payment Methods", ("billing.paymentgateway", "payments.paymentmethod"), "PM"),
    )),
    MenuGroupSpec("Product Management", "PR", ("product", "inventory", "stock", "brand"), (
        MenuItemSpec("Products", ("products.product", "commerce.product"), "PR"),
        MenuItemSpec("Inventory", ("warehouse.inventory", "commerce.stock"), "IN"),
        MenuItemSpec("Stock", ("warehouse.stock", "commerce.stock"), "ST"),
        MenuItemSpec("Product Categories", ("products.category", "commerce.category"), "PC"),
        MenuItemSpec("Brands", ("products.brand", "commerce.brand"), "BR"),
    )),
    MenuGroupSpec("Devices Management", "DV", ("device", "printer", "scanner", "barcode"), (
        MenuItemSpec("Devices", ("enterprise_control.devicesession", "mobileapi.device"), "DV"),
        MenuItemSpec("Device Logs", ("enterprise_control.auditlog", "performance.performancemetric"), "DL"),
        MenuItemSpec("Device Assignment", ("enterprise_control.userworkspace",), "DA"),
        MenuItemSpec("Printers", ("printer_config.printerprofile", "printer_config.printerconfig"), "PR"),
        MenuItemSpec("Barcode Scanners", ("scanner_config.scannerprofile", "scanner_config.scannerconfig"), "BS"),
    )),
    MenuGroupSpec("CRM Management", "CRM", ("crm", "lead", "deal", "pipeline", "follow"), (
        MenuItemSpec("Leads", ("leads.lead", "crm.lead"), "LD"),
        MenuItemSpec("Deals", ("crm.deal",), "DE"),
        MenuItemSpec("Pipelines", ("crm.pipeline",), "PI"),
        MenuItemSpec("Follow Ups", ("crm.followup", "leads.followup"), "FU"),
    )),
    MenuGroupSpec("AI Management", "AI", ("ai", "prompt", "ocr", "insight"), (
        MenuItemSpec("AI Settings", ("core.enterprisesetting", "ai_engine.aisettings"), "AS"),
        MenuItemSpec("AI Prompts", ("ai_engine.aiprompt", "chatbot.chatbotflow"), "AP"),
        MenuItemSpec("AI Logs", ("ai_engine.ailog", "enterprise_control.auditlog"), "AL"),
        MenuItemSpec("AI Usage", ("ai_insights.aiusage", "performance.performancemetric"), "AU"),
    )),
)


@register.simple_tag(takes_context=True)
def enterprise_admin_menu(context):
    request = context.get("request")
    registry = _registered_admin_models(request)
    used: set[str] = set()
    groups = []

    for spec in GROUPS:
        items = []
        for item_spec in spec.items:
            item = _first_available_item(item_spec, registry)
            if item:
                used.add(item["model_key"])
                items.append(item)
        auto_items = _auto_items_for_group(spec, registry, used)
        for item in auto_items:
            used.add(item["model_key"])
        items.extend(auto_items)
        if items:
            groups.append(
                {
                    "title": spec.title,
                    "icon": spec.icon,
                    "items": sorted(items, key=lambda row: row["label"]),
                    "count": len(items),
                }
            )

    remaining = [item for key, item in registry.items() if key not in used]
    if remaining:
        groups.append(
            {
                "title": "Other Management",
                "icon": "OT",
                "items": sorted(remaining, key=lambda row: row["label"]),
                "count": len(remaining),
            }
        )

    return {
        "groups": groups,
        "total": sum(group["count"] for group in groups),
        "dashboard_url": reverse("admin:index"),
    }


def _registered_admin_models(request) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for model, model_admin in admin.site._registry.items():
        opts = model._meta
        key = f"{opts.app_label}.{opts.model_name}".lower()
        if not _can_view_model(request, model_admin):
            continue
        try:
            url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        except NoReverseMatch:
            continue
        add_url = ""
        try:
            if request and model_admin.has_add_permission(request):
                add_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_add")
        except NoReverseMatch:
            add_url = ""
        rows[key] = {
            "label": str(opts.verbose_name_plural).title(),
            "model_key": key,
            "app_label": opts.app_label,
            "model_name": opts.model_name,
            "url": url,
            "add_url": add_url,
            "icon": _initials(str(opts.verbose_name_plural)),
        }
    return rows


def _can_view_model(request, model_admin) -> bool:
    if request is None:
        return True
    try:
        perms = model_admin.get_model_perms(request)
        return bool(perms and any(perms.values()))
    except Exception:
        return False


def _first_available_item(spec: MenuItemSpec, registry: dict[str, dict]) -> dict | None:
    for model_key in spec.models:
        item = registry.get(model_key.lower())
        if item:
            item = {**item, "label": spec.label, "icon": spec.icon}
            return item
    return None


def _auto_items_for_group(spec: MenuGroupSpec, registry: dict[str, dict], used: set[str]) -> list[dict]:
    matches = []
    for key, item in registry.items():
        if key in used:
            continue
        haystack = f"{item['app_label']} {item['model_name']} {item['label']}".lower()
        if any(keyword in haystack for keyword in spec.keywords):
            matches.append(item)
    return matches[:12]


def _initials(value: str) -> str:
    parts = [part for part in value.replace("&", " ").replace("-", " ").split() if part]
    if not parts:
        return "IT"
    return "".join(part[0] for part in parts[:2]).upper()
