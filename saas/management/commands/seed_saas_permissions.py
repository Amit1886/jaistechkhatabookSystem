from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from saas.models import (
    Department,
    PermissionMaster,
    PermissionNode,
    Role,
    RolePermission,
    RoleTemplate,
    RoleTemplatePermission,
)


DEFAULT_PERMISSIONS = [
    # SaaS/RBAC
    ("rbac_view", "View RBAC registry", "saas", "Debug/inspect RBAC registry (backend-only)."),
    # Users / sub-users
    ("subuser_create", "Create sub-users", "accounts", "Owner can create subordinate users."),
    ("subuser_update", "Update sub-users", "accounts", "Owner can update subordinate users."),
    ("subuser_deactivate", "Deactivate sub-users", "accounts", "Owner can deactivate subordinate users."),
    # Billing/ERP permissions (examples)
    ("create_order", "Create orders", "billing", "Create sales/purchase orders."),
    ("create_invoice", "Create invoices", "billing", "Create invoices."),
    ("apply_discount", "Apply discounts", "billing", "Apply discounts/coupons."),
    # Warehouse
    ("stock_inward", "Stock inward", "warehouse", "Record inward stock."),
    ("stock_outward", "Stock outward", "warehouse", "Record outward stock."),
    ("stock_adjust", "Stock adjust", "warehouse", "Adjust stock levels."),
    # Accounts/Ledger
    ("ledger_view", "View ledger", "ledger", "View ledger entries."),
    ("ledger_post", "Post to ledger", "ledger", "Post ledger entries."),
    ("payment_record", "Record payments", "ledger", "Record payments/receipts."),
    # Vendor/storefront
    ("vendor_access", "Vendor access", "storefront", "Access vendor dashboard."),
    ("store_settings", "Store settings", "storefront", "Manage store settings."),
]


DEFAULT_ROLES = {
    "owner": {
        # Owner is treated as all-access in `accounts.User.has_permission()`.
        # These are still registered for UI/registry completeness.
        "subuser_create",
        "subuser_update",
        "subuser_deactivate",
        "create_order",
        "create_invoice",
        "apply_discount",
        "stock_inward",
        "stock_outward",
        "stock_adjust",
        "ledger_view",
        "ledger_post",
        "payment_record",
        "vendor_access",
        "store_settings",
    },
    "manager": {"approve_request", "view_reports"},
    "billing": {"create_order", "create_invoice", "apply_discount"},
    "warehouse": {"stock_inward", "stock_outward", "stock_adjust"},
    "accounts": {"ledger_view", "ledger_post", "payment_record"},
    "vendor": {"vendor_access", "store_settings"},
    "staff": set(),
}


class Command(BaseCommand):
    help = "Seed SaaS PermissionMaster/Role registry (safe to run multiple times)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        updated = 0

        for key, label, module, description in DEFAULT_PERMISSIONS:
            obj, was_created = PermissionMaster.objects.update_or_create(
                key=key,
                defaults={
                    "label": label,
                    "module": module,
                    "description": description,
                    "is_active": True,
                },
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        # ---- APGS seed (Department/PermissionNode/RoleTemplate) ----
        dept_cache: dict[str, Department] = {}
        for _, _, module, _ in DEFAULT_PERMISSIONS:
            if not module:
                continue
            dk = module.strip().lower().replace(" ", "_")
            if dk in dept_cache:
                continue
            dept_cache[dk], _ = Department.objects.get_or_create(key=dk[:60], defaults={"name": module.title(), "is_active": True})

        pnode_created = 0
        for key, label, module, description in DEFAULT_PERMISSIONS:
            dept = dept_cache.get((module or "").strip().lower().replace(" ", "_"))
            obj, was_created = PermissionNode.objects.update_or_create(
                key=key,
                defaults={
                    "label": label,
                    "module": module,
                    "description": description,
                    "department": dept,
                    "is_active": True,
                },
            )
            pnode_created += 1 if was_created else 0

        role_created = 0
        rp_created = 0
        for role_key, perm_keys in DEFAULT_ROLES.items():
            role, was_created = Role.objects.get_or_create(
                key=role_key,
                defaults={"label": role_key.title(), "is_system": True, "is_active": True},
            )
            role_created += 1 if was_created else 0

            # APGS role templates mirror system roles (same key)
            rt, _ = RoleTemplate.objects.get_or_create(
                key=role_key,
                defaults={"label": role_key.title(), "is_system": True, "is_active": True},
            )

            for perm_key in perm_keys:
                perm = PermissionMaster.objects.filter(key=perm_key).first()
                if not perm:
                    perm = PermissionMaster.objects.create(
                        key=perm_key,
                        label=perm_key.replace("_", " ").title(),
                        module="misc",
                        description="Seeded by role defaults.",
                        is_active=True,
                    )
                    created += 1
                _, was_rp_created = RolePermission.objects.get_or_create(role=role, permission=perm)
                rp_created += 1 if was_rp_created else 0

                # APGS edge
                pnode = PermissionNode.objects.filter(key=perm_key).first()
                if pnode:
                    RoleTemplatePermission.objects.get_or_create(
                        role=rt,
                        permission=pnode,
                        defaults={"effect": RoleTemplatePermission.EFFECT_ALLOW},
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded: "
                f"PermissionMaster(created={created}, updated={updated}); "
                f"PermissionNode(created={pnode_created}); "
                f"Roles(created={role_created}); RolePermission(created={rp_created})"
            )
        )
