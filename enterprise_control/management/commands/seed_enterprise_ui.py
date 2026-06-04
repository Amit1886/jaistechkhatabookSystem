from django.core.management.base import BaseCommand

from enterprise_control.models import DynamicButton, DynamicMenuItem, DynamicModule, ThemeConfig, Workspace


MODULES = [
    ("dashboard", "Command Center", "dashboard", "#0F766E", "/dashboard", "/accounts/dashboard/", 1, {"mode": "dashboard"}),
    ("pos", "POS", "point_of_sale", "#2563EB", "/pos", "/pos/ui/", 2, {"mode": "pos", "model_key": "orders.order"}),
    ("orders", "Orders", "shopping_cart", "#0EA5E9", "/orders", "/api/v1/orders/", 3, {"model_key": "orders.order"}),
    ("billing", "Billing", "receipt_long", "#10B981", "/billing", "/billing/", 4, {"model_key": "billing.billinginvoice"}),
    ("products", "Products", "inventory_2", "#F59E0B", "/products", "/commerce/products/", 5, {"model_key": "products.product"}),
    ("reports", "Reports", "bar_chart", "#EF4444", "/reports", "/reports/", 6, {"mode": "reports"}),
    ("selfcheckout", "SelfCheckout", "qr_code_scanner", "#7C3AED", "/self-checkout", "/pos/self-checkout/", 7, {"mode": "kiosk", "model_key": "orders.order"}),
    ("crm", "CRM", "groups", "#06B6D4", "/crm", "/api/v1/crm/", 8, {"model_key": "leads.lead"}),
]


class Command(BaseCommand):
    help = "Seed enterprise dynamic UI modules, app launcher, buttons, sidebar, and theme."

    def handle(self, *args, **options):
        theme, _ = ThemeConfig.objects.update_or_create(
            key="default-enterprise",
            defaults={
                "name": "Default Enterprise",
                "brand_name": "Billentra",
                "primary": "#0F766E",
                "secondary": "#2563EB",
                "accent": "#F59E0B",
                "surface": "#F8FAFC",
                "dark_surface": "#0B1120",
                "radius": 8,
                "density": "comfortable",
                "is_default": True,
                "is_active": True,
            },
        )
        workspace, _ = Workspace.objects.update_or_create(
            key="enterprise-default",
            defaults={
                "name": "Enterprise Workspace",
                "landing_route": "/dashboard",
                "platform": "app",
                "is_default": True,
                "is_active": True,
                "order": 1,
                "layout_schema": {"columns": 12, "density": "comfortable", "responsive": True},
            },
        )

        module_keys = []
        for key, title, icon, color, route, web_url, order, module_settings in MODULES:
            module, _ = DynamicModule.objects.update_or_create(
                key=key,
                defaults={
                    "name": title,
                    "icon": icon,
                    "color": color,
                    "app_route": route,
                    "web_url": web_url,
                    "api_namespace": "/fastapi/crud",
                    "access_platforms": ["web", "app", "pos", "kiosk", "api"],
                    "required_permissions": [],
                    "settings": module_settings,
                    "order": order,
                    "is_core": True,
                    "is_enabled": True,
                },
            )
            module_keys.append(key)
            DynamicButton.objects.update_or_create(
                key=f"quick-{key}",
                defaults={
                    "label": title,
                    "module": module,
                    "workspace": workspace,
                    "action_type": "module",
                    "route": route,
                    "icon": icon,
                    "color": color,
                    "gradient": [color, "#0B1120"],
                    "shape": "rounded",
                    "animation": "smooth",
                    "platform_access": ["web", "app", "pos", "kiosk"],
                    "order": order,
                    "is_primary": order <= 4,
                    "is_enabled": True,
                },
            )
            DynamicMenuItem.objects.update_or_create(
                key=f"menu-{key}",
                defaults={
                    "title": title,
                    "workspace": workspace,
                    "module": module,
                    "icon": icon,
                    "route": route,
                    "color": color,
                    "platform_access": ["web", "app", "pos", "kiosk"],
                    "order": order,
                    "is_group": False,
                    "is_enabled": True,
                },
            )

        workspace.module_keys = module_keys
        workspace.save(update_fields=["module_keys", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"Seeded enterprise UI workspace '{workspace.key}' with theme '{theme.key}'"))
