from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from saas.models import Department, PermissionNode, RoleTemplate, RoleTemplatePermission

from enterprise_control.models import DashboardWidget, DynamicModule, PermissionTemplate, ThemeConfig, Workspace


MODULES = [
    ("dashboard", "Dashboard", "layout-dashboard", "#0F766E", "/accounts/dashboard/", "/dashboard", "/api/dashboard/", ["web", "app", "api"], 10),
    ("pos", "POS", "shopping-bag", "#2563EB", "/pos/ui/", "/pos", "/api/v1/pos/", ["web", "app", "pos", "api"], 20),
    ("selfcheckout", "Self Checkout", "scan-line", "#7C3AED", "/pos/self-checkout/", "/self-checkout", "/api/v1/pos/", ["web", "app", "kiosk", "api"], 30),
    ("inventory", "Inventory", "boxes", "#F59E0B", "/commerce/products/", "/inventory", "/api/v1/products/", ["web", "app", "api"], 40),
    ("billing", "Billing", "receipt", "#10B981", "/billing/", "/billing", "/api/v1/orders/", ["web", "app", "pos", "api"], 50),
    ("crm", "CRM", "users", "#0EA5E9", "/api/v1/crm/", "/crm", "/api/v1/crm/", ["web", "app", "api"], 60),
    ("ecommerce", "Ecommerce", "store", "#EC4899", "/store/", "/store", "/api/", ["web", "app", "api"], 70),
    ("suppliers", "Suppliers", "truck", "#64748B", "/portal/", "/suppliers", "/api/v1/distribution/", ["web", "app", "api"], 80),
    ("orders", "Orders", "clipboard-list", "#14B8A6", "/commerce/orders/", "/orders", "/api/v1/orders/", ["web", "app", "api"], 90),
    ("reports", "Reports", "bar-chart-3", "#EF4444", "/reports/", "/reports", "/api/reports/", ["web", "app", "api"], 100),
    ("analytics", "Analytics", "line-chart", "#8B5CF6", "/smart-bi/", "/analytics", "/api/analytics/", ["web", "app", "api"], 110),
]

ROLES = {
    "admin": ["web_access", "app_access", "pos_access", "kiosk_access", "api_access"],
    "pos_user": ["web_access", "app_access", "pos_access", "pos_view", "pos_create", "billing_view", "billing_create", "inventory_view", "print_pos"],
    "billing_user": ["web_access", "app_access", "api_access", "billing_view", "billing_create", "billing_edit", "orders_view", "orders_create", "print_billing"],
    "crm_user": ["web_access", "app_access", "api_access", "crm_view", "crm_create", "crm_edit", "reports_view"],
    "supplier": ["web_access", "app_access", "api_access", "suppliers_view", "orders_view", "billing_view"],
    "ecommerce_vendor": ["web_access", "app_access", "api_access", "ecommerce_view", "ecommerce_create", "products_view", "orders_view", "analytics_view"],
    "ecommerce_customer": ["web_access", "app_access", "ecommerce_view", "orders_view"],
    "customer": ["web_access", "app_access", "billing_view", "orders_view"],
    "accountant": ["web_access", "api_access", "billing_view", "billing_edit", "reports_view", "analytics_view", "export_reports"],
    "kiosk_user": ["kiosk_access", "selfcheckout_view", "selfcheckout_create", "billing_create"],
    "self_checkout_user": ["kiosk_access", "selfcheckout_view", "selfcheckout_create", "billing_create"],
    "agent": ["app_access", "api_access", "crm_view", "crm_create", "orders_create"],
    "staff": ["web_access", "app_access", "dashboard_view"],
}

WORKSPACES = [
    ("admin_workspace", "Admin Control Workspace", "admin", "/superadmin/", ["dashboard", "pos", "inventory", "billing", "crm", "ecommerce", "reports", "analytics"], True, 10),
    ("pos_workspace", "POS Workspace", "pos_user", "/pos/ui/", ["pos", "billing", "inventory", "orders"], False, 20),
    ("supplier_workspace", "Supplier Workspace", "supplier", "/portal/", ["suppliers", "orders", "billing"], False, 30),
    ("crm_workspace", "CRM Workspace", "crm_user", "/api/v1/crm/", ["crm", "reports", "analytics"], False, 40),
    ("vendor_workspace", "Vendor Workspace", "ecommerce_vendor", "/store/", ["ecommerce", "orders", "inventory", "analytics"], False, 50),
    ("customer_workspace", "Customer Workspace", "customer", "/accounts/customer-dashboard/", ["ecommerce", "orders", "billing"], False, 60),
    ("kiosk_workspace", "Kiosk Workspace", "kiosk_user", "/pos/self-checkout/", ["selfcheckout", "billing"], False, 70),
]


class Command(BaseCommand):
    help = "Seed enterprise roles, permissions, modules, workspaces, widgets, and theme."

    @transaction.atomic
    def handle(self, *args, **options):
        dept, _ = Department.objects.get_or_create(key="enterprise", defaults={"name": "Enterprise Control", "is_active": True})

        permission_keys = set()
        for role_perms in ROLES.values():
            permission_keys.update(role_perms)
        for module_key, *_ in MODULES:
            permission_keys.update({f"{module_key}_{action}" for action in ("view", "create", "edit", "delete", "export", "print", "approve")})

        for key in sorted(permission_keys):
            PermissionNode.objects.update_or_create(
                key=key,
                defaults={
                    "label": key.replace("_", " ").title(),
                    "module": key.split("_", 1)[0],
                    "department": dept,
                    "is_active": True,
                },
            )

        roles = {}
        for role_key, perm_keys in ROLES.items():
            role, _ = RoleTemplate.objects.update_or_create(
                key=role_key,
                defaults={"label": role_key.replace("_", " ").title(), "department": dept, "is_system": True, "is_active": True},
            )
            roles[role_key] = role
            for perm_key in perm_keys:
                perm = PermissionNode.objects.get(key=perm_key)
                RoleTemplatePermission.objects.update_or_create(role=role, permission=perm, defaults={"effect": "allow"})
            PermissionTemplate.objects.update_or_create(
                key=role_key,
                defaults={
                    "name": role.label,
                    "role": role,
                    "permission_keys": list(perm_keys),
                    "platform_access": {p: p in perm_keys for p in ("web_access", "app_access", "pos_access", "kiosk_access", "api_access")},
                    "is_system": True,
                    "is_active": True,
                },
            )

        modules = {}
        for key, name, icon, color, web_url, app_route, api_namespace, platforms, order in MODULES:
            module, _ = DynamicModule.objects.update_or_create(
                key=key,
                defaults={
                    "name": name,
                    "icon": icon,
                    "color": color,
                    "web_url": web_url,
                    "app_route": app_route,
                    "api_namespace": api_namespace,
                    "access_platforms": platforms,
                    "required_permissions": [f"{key}_view"],
                    "order": order,
                    "is_core": True,
                    "is_enabled": True,
                },
            )
            modules[key] = module

        ThemeConfig.objects.update_or_create(
            key="billentra_enterprise",
            defaults={"name": "Billentra Enterprise", "brand_name": "Billentra", "is_default": True, "is_active": True},
        )

        for key, name, role_key, landing, module_keys, is_default, order in WORKSPACES:
            role = roles.get(role_key)
            workspace, _ = Workspace.objects.update_or_create(
                key=key,
                defaults={
                    "name": name,
                    "role": role,
                    "landing_route": landing,
                    "platform": "web",
                    "module_keys": module_keys,
                    "menu_schema": [{"key": m, "title": modules[m].name, "icon": modules[m].icon, "route": modules[m].app_route or modules[m].web_url} for m in module_keys if m in modules],
                    "layout_schema": {"density": "comfortable", "columns": 12},
                    "is_default": is_default,
                    "is_active": True,
                    "order": order,
                },
            )
            for idx, module_key in enumerate(module_keys[:6], start=1):
                module = modules.get(module_key)
                if not module:
                    continue
                DashboardWidget.objects.update_or_create(
                    workspace=workspace,
                    key=f"{module_key}_status",
                    defaults={
                        "title": f"{module.name} Status",
                        "widget_type": "status",
                        "module": module,
                        "permission_key": f"{module_key}_view",
                        "order": idx * 10,
                        "is_enabled": True,
                    },
                )

        self.stdout.write(self.style.SUCCESS("Enterprise control center seed complete."))
